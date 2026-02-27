"""
MPG Calculator for MX5 Telemetry System

Calculates fuel efficiency (MPG) and estimated range from CAN bus data.

SIMPLIFIED APPROACH:
- Track distance traveled and fuel consumed per trip
- Use simple milestone-based fuel tracking (record when fuel drops by 1%)
- Calculate rolling MPG from recent fuel consumption events
- Persist data for long-term accuracy

Key insight: Fuel sensors have low resolution (~1% steps). Trying to track
tiny per-frame fuel changes with EMA smoothing doesn't work well. Instead,
we track distance between fuel level drops and calculate MPG from that.

Industry Standard Formulas:
- MPG = Distance (miles) / Fuel Used (gallons)
- Range = Remaining Fuel (gallons) × Average MPG

DATA SAFETY:
- Atomic writes (write to temp file, then rename) prevent corruption
- Backup file (.bak) preserves previous good state
- Load validates data and falls back to backup on failure
- Never overwrites good data with empty data (checks file on disk first)
- Startup fuel guard ignores fuel readings until CAN data stabilizes
- File locking prevents multi-instance corruption
"""

import json
import os
import time
import threading
from dataclasses import dataclass
from typing import Optional, List
from pathlib import Path


@dataclass
class FuelMilestone:
    """Records a fuel consumption milestone"""
    fuel_pct: float          # Fuel level when recorded (0-100)
    total_distance: float    # Cumulative distance at this point
    timestamp: float         # Unix timestamp


class MPGCalculator:
    """
    Simplified MPG calculator using milestone-based tracking.
    
    Strategy:
    1. Track cumulative distance traveled
    2. Record fuel level milestones when fuel drops by >= 1%
    3. Calculate MPG from distance between milestones
    4. Use rolling window of recent calculations for display
    5. Persist data to survive restarts
    
    Data Safety:
    - Atomic writes prevent partial-write corruption
    - Backup file allows recovery from corruption
    - Refuses to overwrite higher-mileage data with empty/lower data
    - Startup fuel guard prevents false refuel detection from CAN init delay
    """
    
    # MX5 NC (2006-2015) tank capacity
    TANK_CAPACITY_GAL = 12.7
    
    # Minimum fuel drop to register a milestone (percentage points)
    # Using 2% threshold to filter fuel sensor noise (readings bounce ±4%)
    FUEL_MILESTONE_THRESHOLD = 2.0
    
    # Minimum distance between milestones (prevents noise at low speeds/idle)
    MIN_DISTANCE_FOR_MILESTONE = 1.0  # miles (increased from 0.5 to filter noise)
    
    # Minimum speed to count as driving (filters idle time)
    MIN_DRIVING_SPEED_MPH = 3.0
    
    # How often to save persistent data (seconds)
    SAVE_INTERVAL_SEC = 60.0
    
    # Maximum reasonable MPG (sanity check)
    MAX_REASONABLE_MPG = 50.0
    MIN_REASONABLE_MPG = 10.0
    
    # Number of recent MPG calculations to keep for rolling average
    MAX_RECENT_CALCULATIONS = 20
    
    # EPA default for MX5 NC (used when no data available)
    EPA_DEFAULT_MPG = 26.0
    
    # Startup fuel stabilization period — ignore fuel data for this many seconds
    # after startup to let CAN bus readings stabilize (prevents 0% → real% being
    # detected as a "refuel" event)
    FUEL_STABILIZE_SECONDS = 10.0
    
    def __init__(self, data_dir: str = "/home/pi/MX5-Telemetry/data"):
        """
        Initialize MPG calculator.
        
        Args:
            data_dir: Directory for persistent data storage
        """
        self.data_dir = Path(data_dir)
        self.data_file = self.data_dir / "mpg_data.json"
        self.backup_file = self.data_dir / "mpg_data.json.bak"
        self.lock_file = self.data_dir / "mpg_data.lock"
        
        # Cumulative tracking
        self._total_distance = 0.0        # Lifetime distance
        self._session_distance = 0.0      # Distance this session (since last fuel milestone)
        
        # Fuel tracking
        self._last_fuel_pct = None        # Last recorded fuel percentage
        self._fuel_at_milestone = None    # Fuel % at last milestone
        self._distance_at_milestone = 0.0 # Total distance at last milestone
        
        # Recent MPG calculations for rolling average
        self._recent_mpg_values: List[float] = []
        self._recent_distances: List[float] = []  # Distance for each MPG calculation
        
        # Lifetime totals (for persistence)
        self._lifetime_miles = 0.0
        self._lifetime_gallons = 0.0
        
        # State tracking
        self._engine_was_running = False
        self._last_update_time = 0.0
        self._last_save_time = 0.0
        self._start_time = 0.0            # When start() was called
        self._fuel_stabilized = False      # True after FUEL_STABILIZE_SECONDS
        self._valid_fuel_readings = 0      # Count of non-zero fuel readings
        
        # Output values (thread-safe reads)
        self._lock = threading.Lock()
        self._average_mpg = self.EPA_DEFAULT_MPG
        self._range_miles = 0
        self._current_fuel_pct = 0.0
        
        # Running flag
        self._running = False
        
        # Debug tracking
        self._debug_counter = 0
    
    def start(self):
        """Start the calculator and load persistent data"""
        self._running = True
        self._start_time = time.time()
        self._fuel_stabilized = False
        self._valid_fuel_readings = 0
        self._load_data()
        print(f"MPG Calculator started. Lifetime: {self._lifetime_miles:.1f} mi, "
              f"{self._lifetime_gallons:.2f} gal, avg MPG: {self._average_mpg:.1f}")
    
    def stop(self):
        """Stop the calculator and save data"""
        self._running = False
        self._save_data()
        print("MPG Calculator stopped and data saved.")
    
    @property
    def instant_mpg(self) -> float:
        """Get instantaneous MPG (same as average for now)"""
        with self._lock:
            return self._average_mpg
    
    @property
    def average_mpg(self) -> float:
        """Get average MPG"""
        with self._lock:
            return self._average_mpg
    
    @property
    def range_miles(self) -> int:
        """Get estimated range in miles"""
        with self._lock:
            return self._range_miles
    
    @property
    def smoothed_fuel_pct(self) -> float:
        """Get current fuel percentage"""
        with self._lock:
            return self._current_fuel_pct
    
    @property
    def trip_mpg(self) -> float:
        """Get trip MPG (same as average for simplicity)"""
        return self.average_mpg
    
    @property
    def trip_distance(self) -> float:
        """Get current session distance since last milestone"""
        return self._session_distance
    
    def update(self, speed_mph: float, raw_fuel_pct: float, 
               engine_running: bool, dt_seconds: float = None):
        """
        Update MPG calculations with latest CAN data.
        
        Args:
            speed_mph: Current vehicle speed in MPH
            raw_fuel_pct: Raw fuel level percentage from CAN (0-100)
            engine_running: True if engine is running (RPM > 0)
            dt_seconds: Time since last update (auto-calculated if None)
        """
        if not self._running:
            return
        
        current_time = time.time()
        
        # Calculate dt if not provided
        if dt_seconds is None:
            if self._last_update_time > 0:
                dt_seconds = current_time - self._last_update_time
            else:
                dt_seconds = 0.033  # Default to ~30Hz
        
        # Clamp dt to reasonable range (handles pauses/delays)
        dt_seconds = min(dt_seconds, 1.0)
        self._last_update_time = current_time
        
        # Validate fuel reading — treat 0% as uninitialized (CAN hasn't sent data yet)
        # Real fuel level will never be exactly 0.0% while engine is running
        if raw_fuel_pct <= 0 or raw_fuel_pct > 100:
            raw_fuel_pct = self._current_fuel_pct if self._current_fuel_pct > 0 else -1
            if raw_fuel_pct <= 0:
                # No valid fuel data yet — still accumulate distance but skip fuel tracking
                if engine_running and speed_mph >= self.MIN_DRIVING_SPEED_MPH:
                    distance_increment = (speed_mph / 3600.0) * dt_seconds
                    self._session_distance += distance_increment
                    self._total_distance += distance_increment
                    self._lifetime_miles += distance_increment
                # Periodic save (distance still matters)
                if current_time - self._last_save_time >= self.SAVE_INTERVAL_SEC:
                    self._save_data()
                    self._last_save_time = current_time
                return
        
        # Fuel stabilization guard: after startup, wait for CAN fuel data to stabilize
        # before doing any fuel-based tracking (milestones, refuel detection).
        # This prevents the common bug where fuel reads 0% → real% on startup,
        # which triggers a false "refuel detected" that resets session data.
        if not self._fuel_stabilized:
            if raw_fuel_pct > 0:
                self._valid_fuel_readings += 1
            time_since_start = current_time - self._start_time
            if time_since_start >= self.FUEL_STABILIZE_SECONDS and self._valid_fuel_readings >= 30:
                self._fuel_stabilized = True
                # Initialize fuel tracking from the stabilized reading
                if self._last_fuel_pct is None or self._last_fuel_pct <= 0:
                    self._last_fuel_pct = raw_fuel_pct
                if self._fuel_at_milestone is None or self._fuel_at_milestone <= 0:
                    self._fuel_at_milestone = raw_fuel_pct
                print(f"MPG: Fuel stabilized at {raw_fuel_pct:.1f}% "
                      f"(after {time_since_start:.1f}s, {self._valid_fuel_readings} readings)")
            else:
                # Still accumulate distance during stabilization
                if engine_running and speed_mph >= self.MIN_DRIVING_SPEED_MPH:
                    distance_increment = (speed_mph / 3600.0) * dt_seconds
                    self._session_distance += distance_increment
                    self._total_distance += distance_increment
                    self._lifetime_miles += distance_increment
                # Store fuel for display even before stabilized
                with self._lock:
                    self._current_fuel_pct = raw_fuel_pct
                self._update_outputs(raw_fuel_pct)
                # Periodic save
                if current_time - self._last_save_time >= self.SAVE_INTERVAL_SEC:
                    self._save_data()
                    self._last_save_time = current_time
                return
        
        # Store current fuel for display
        with self._lock:
            self._current_fuel_pct = raw_fuel_pct
        
        # Initialize fuel tracking if needed (only after stabilization)
        if self._last_fuel_pct is None or self._last_fuel_pct <= 0:
            self._last_fuel_pct = raw_fuel_pct
            self._fuel_at_milestone = raw_fuel_pct
            print(f"MPG: Initialized fuel tracking at {raw_fuel_pct:.1f}%")
        
        # Accumulate distance if driving
        if engine_running and speed_mph >= self.MIN_DRIVING_SPEED_MPH:
            distance_increment = (speed_mph / 3600.0) * dt_seconds  # miles
            self._session_distance += distance_increment
            self._total_distance += distance_increment
            self._lifetime_miles += distance_increment
        
        # Check for fuel milestone (fuel dropped by threshold)
        fuel_drop = self._fuel_at_milestone - raw_fuel_pct if self._fuel_at_milestone else 0
        
        if (fuel_drop >= self.FUEL_MILESTONE_THRESHOLD and 
            self._session_distance >= self.MIN_DISTANCE_FOR_MILESTONE):
            
            # Calculate MPG for this segment
            gallons_used = (fuel_drop / 100.0) * self.TANK_CAPACITY_GAL
            segment_mpg = self._session_distance / gallons_used if gallons_used > 0 else 0
            
            # Sanity check
            if self.MIN_REASONABLE_MPG <= segment_mpg <= self.MAX_REASONABLE_MPG:
                # Record this calculation
                self._recent_mpg_values.append(segment_mpg)
                self._recent_distances.append(self._session_distance)
                
                # Trim to max size
                while len(self._recent_mpg_values) > self.MAX_RECENT_CALCULATIONS:
                    self._recent_mpg_values.pop(0)
                    self._recent_distances.pop(0)
                
                # Accumulate to lifetime
                self._lifetime_gallons += gallons_used
                
                print(f"MPG: Milestone! Fuel {self._fuel_at_milestone:.1f}% -> {raw_fuel_pct:.1f}% "
                      f"({fuel_drop:.1f}% drop = {gallons_used:.2f}gal), "
                      f"distance: {self._session_distance:.1f}mi, MPG: {segment_mpg:.1f}, "
                      f"lifetime: {self._lifetime_miles:.1f}mi / {self._lifetime_gallons:.2f}gal")
            else:
                print(f"MPG: Skipping unreasonable MPG: {segment_mpg:.1f} "
                      f"(fuel drop {fuel_drop:.1f}%, distance {self._session_distance:.1f}mi)")
            
            # Reset for next segment
            self._fuel_at_milestone = raw_fuel_pct
            self._session_distance = 0.0
        
        # Detect refueling (fuel increased significantly)
        # Only if we have valid prior data and the jump is large enough to be real
        if (self._last_fuel_pct is not None and self._last_fuel_pct > 0 and
                raw_fuel_pct > self._last_fuel_pct + 10.0):  # 10% increase = likely refueled
            
            # IMPORTANT: Count the fuel consumed between last milestone and refuel point.
            # Without this, the "tail end" of each tank (last milestone → refuel) is lost,
            # which causes gallons to be severely undercounted over time.
            if self._fuel_at_milestone is not None and self._fuel_at_milestone > 0:
                tail_drop = self._fuel_at_milestone - self._last_fuel_pct
                if tail_drop > 0:
                    tail_gallons = (tail_drop / 100.0) * self.TANK_CAPACITY_GAL
                    self._lifetime_gallons += tail_gallons
                    
                    # Record MPG for this final segment if enough distance
                    if self._session_distance >= self.MIN_DISTANCE_FOR_MILESTONE and tail_gallons > 0:
                        tail_mpg = self._session_distance / tail_gallons
                        if self.MIN_REASONABLE_MPG <= tail_mpg <= self.MAX_REASONABLE_MPG:
                            self._recent_mpg_values.append(tail_mpg)
                            self._recent_distances.append(self._session_distance)
                            while len(self._recent_mpg_values) > self.MAX_RECENT_CALCULATIONS:
                                self._recent_mpg_values.pop(0)
                                self._recent_distances.pop(0)
                    
                    print(f"MPG: Refuel detected! {self._last_fuel_pct:.1f}% -> {raw_fuel_pct:.1f}%. "
                          f"Counted tail: {self._fuel_at_milestone:.1f}% -> {self._last_fuel_pct:.1f}% "
                          f"= {tail_gallons:.3f}gal over {self._session_distance:.1f}mi. "
                          f"Lifetime: {self._lifetime_miles:.1f}mi / {self._lifetime_gallons:.2f}gal")
                else:
                    print(f"MPG: Refuel detected! {self._last_fuel_pct:.1f}% -> {raw_fuel_pct:.1f}% (no tail to count)")
            else:
                print(f"MPG: Refuel detected! {self._last_fuel_pct:.1f}% -> {raw_fuel_pct:.1f}%")
            
            self._fuel_at_milestone = raw_fuel_pct
            self._session_distance = 0.0
        
        self._last_fuel_pct = raw_fuel_pct
        
        # Update output values
        self._update_outputs(raw_fuel_pct)
        
        # Periodic save
        if current_time - self._last_save_time >= self.SAVE_INTERVAL_SEC:
            self._save_data()
            self._last_save_time = current_time
        
        # Debug output periodically
        self._debug_counter += 1
        if self._debug_counter >= 300:  # Every ~10 seconds at 30Hz
            self._debug_counter = 0
            if engine_running:
                print(f"MPG DEBUG: fuel={raw_fuel_pct:.1f}%, session_dist={self._session_distance:.2f}mi, "
                      f"avg={self._average_mpg:.1f}, range={self._range_miles}mi, "
                      f"milestone_fuel={self._fuel_at_milestone:.1f}%, "
                      f"lifetime={self._lifetime_miles:.1f}mi")
    
    def _update_outputs(self, raw_fuel_pct: float):
        """Update thread-safe output values"""
        with self._lock:
            # Calculate average MPG from lifetime totals (most reliable)
            # Recent milestones are used as a supplement for responsiveness
            if self._lifetime_gallons > 0.5:
                # Enough lifetime data — use 80% lifetime, 20% recent for some responsiveness
                lifetime_mpg = self._lifetime_miles / self._lifetime_gallons
                if self._recent_mpg_values and self._recent_distances:
                    total_dist = sum(self._recent_distances)
                    if total_dist > 0:
                        weighted_sum = sum(mpg * dist for mpg, dist in 
                                         zip(self._recent_mpg_values, self._recent_distances))
                        recent_mpg = weighted_sum / total_dist
                        self._average_mpg = 0.8 * lifetime_mpg + 0.2 * recent_mpg
                    else:
                        self._average_mpg = lifetime_mpg
                else:
                    self._average_mpg = lifetime_mpg
            elif self._lifetime_gallons > 0.1:
                # Some lifetime data — use it directly
                self._average_mpg = self._lifetime_miles / self._lifetime_gallons
            elif self._recent_mpg_values and self._recent_distances:
                total_dist = sum(self._recent_distances)
                if total_dist > 0:
                    weighted_sum = sum(mpg * dist for mpg, dist in 
                                     zip(self._recent_mpg_values, self._recent_distances))
                    self._average_mpg = weighted_sum / total_dist
            else:
                # No data yet - use EPA default
                self._average_mpg = self.EPA_DEFAULT_MPG
            
            # Clamp to reasonable range
            self._average_mpg = max(self.MIN_REASONABLE_MPG, 
                                   min(self._average_mpg, self.MAX_REASONABLE_MPG))
            
            # Calculate range
            if raw_fuel_pct > 0:
                remaining_gal = (raw_fuel_pct / 100.0) * self.TANK_CAPACITY_GAL
                self._range_miles = int(remaining_gal * self._average_mpg)
            else:
                self._range_miles = 0
    
    def _load_data(self):
        """Load persistent data from JSON file with backup fallback.
        
        Tries the main file first, falls back to backup if main is corrupt/empty.
        Never starts fresh if a file exists — that protects against race conditions
        where another instance might be writing at the same moment.
        """
        data = None
        source = None
        
        # Try main file first, then backup
        for filepath, label in [(self.data_file, "main"), (self.backup_file, "backup")]:
            try:
                if filepath.exists() and filepath.stat().st_size > 10:
                    with open(filepath, 'r') as f:
                        candidate = json.load(f)
                    # Validate: must have positive total_miles or be genuinely new
                    if isinstance(candidate, dict) and candidate.get('total_miles', 0) >= 0:
                        if data is None or candidate.get('total_miles', 0) > data.get('total_miles', 0):
                            data = candidate
                            source = label
            except (json.JSONDecodeError, OSError, ValueError) as e:
                print(f"MPG: Error reading {label} file ({filepath}): {e}")
                continue
        
        if data:
            # Restore data
            self._lifetime_miles = max(0, data.get('total_miles', 0.0))
            self._lifetime_gallons = max(0, data.get('total_gallons', 0.0))
            self._recent_mpg_values = data.get('recent_mpg_values', [])
            self._recent_distances = data.get('recent_distances', [])
            self._fuel_at_milestone = data.get('fuel_at_milestone', None)
            self._session_distance = max(0, data.get('session_distance', 0.0))
            self._last_fuel_pct = data.get('last_fuel_pct', None)
            
            # Validate loaded MPG values  
            valid_mpgs = []
            valid_dists = []
            for mpg, dist in zip(self._recent_mpg_values, self._recent_distances):
                if self.MIN_REASONABLE_MPG <= mpg <= self.MAX_REASONABLE_MPG and dist > 0:
                    valid_mpgs.append(mpg)
                    valid_dists.append(dist)
            self._recent_mpg_values = valid_mpgs
            self._recent_distances = valid_dists
            
            # Calculate initial average - prefer lifetime data
            if self._lifetime_gallons > 0.1:
                self._average_mpg = self._lifetime_miles / self._lifetime_gallons
            elif self._recent_distances and sum(self._recent_distances) > 0:
                total_dist = sum(self._recent_distances)
                weighted_sum = sum(m * d for m, d in zip(self._recent_mpg_values, self._recent_distances))
                self._average_mpg = weighted_sum / total_dist
            
            print(f"MPG: Loaded from {source} — {len(self._recent_mpg_values)} recent calculations, "
                  f"lifetime: {self._lifetime_miles:.1f}mi / {self._lifetime_gallons:.2f}gal, "
                  f"session_dist: {self._session_distance:.2f}mi, "
                  f"fuel_at_milestone: {self._fuel_at_milestone}")
        else:
            print("MPG: No existing data file, starting fresh")
    
    def _save_data(self):
        """Save persistent data using atomic write with backup.
        
        Safety measures:
        1. Check if file on disk has MORE miles than us — if so, don't overwrite
           (another instance may have accumulated more data)
        2. Back up the current file before overwriting
        3. Write to a temp file first, then atomically rename
        """
        try:
            # Ensure directory exists
            self.data_dir.mkdir(parents=True, exist_ok=True)
            
            # Safety check: don't overwrite higher-mileage data
            # This protects against instance A (with stale data) overwriting instance B's good data
            if self.data_file.exists():
                try:
                    with open(self.data_file, 'r') as f:
                        existing = json.load(f)
                    existing_miles = existing.get('total_miles', 0)
                    # If the file on disk has significantly more miles, something is wrong
                    # with our instance — refuse to overwrite
                    if existing_miles > self._lifetime_miles + 5.0:
                        # Reload from disk instead of overwriting
                        print(f"MPG: SAFETY — disk has {existing_miles:.1f}mi vs our {self._lifetime_miles:.1f}mi. "
                              f"Reloading from disk to prevent data loss.")
                        self._load_data()
                        return
                except (json.JSONDecodeError, OSError):
                    pass  # File is corrupt, safe to overwrite
            
            data = {
                'total_miles': self._lifetime_miles,
                'total_gallons': self._lifetime_gallons,
                'recent_mpg_values': self._recent_mpg_values,
                'recent_distances': self._recent_distances,
                'fuel_at_milestone': self._fuel_at_milestone,
                'session_distance': self._session_distance,
                'last_fuel_pct': self._last_fuel_pct,
                'last_save_time': time.time(),
                'calculated_avg_mpg': self._average_mpg,
                '_comment': 'MPG data for MX5 Telemetry. Uses milestone-based tracking.'
            }
            
            # Step 1: Back up current file (if it exists and has data)
            if self.data_file.exists() and self.data_file.stat().st_size > 10:
                try:
                    import shutil
                    shutil.copy2(str(self.data_file), str(self.backup_file))
                except OSError:
                    pass  # Backup failure is non-critical
            
            # Step 2: Write to temp file, then atomic rename
            tmp_file = self.data_file.with_suffix('.tmp')
            with open(tmp_file, 'w') as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            
            # Atomic rename (on POSIX systems, rename is atomic if same filesystem)
            os.replace(str(tmp_file), str(self.data_file))
                
        except Exception as e:
            print(f"MPG: Error saving data: {e}")
    
    def reset_lifetime_data(self):
        """Reset all lifetime statistics (use with caution)"""
        print("MPG: Resetting all data")
        self._lifetime_miles = 0.0
        self._lifetime_gallons = 0.0
        self._recent_mpg_values = []
        self._recent_distances = []
        self._fuel_at_milestone = None
        self._session_distance = 0.0
        self._average_mpg = self.EPA_DEFAULT_MPG
        self._save_data()
    
    def reset_trip(self):
        """Reset current session data"""
        self._session_distance = 0.0
        if self._last_fuel_pct is not None:
            self._fuel_at_milestone = self._last_fuel_pct


# Singleton instance for easy import
_calculator_instance: Optional[MPGCalculator] = None


def get_mpg_calculator(data_dir: str = "/home/pi/MX5-Telemetry/data") -> MPGCalculator:
    """Get or create the global MPG calculator instance"""
    global _calculator_instance
    if _calculator_instance is None:
        _calculator_instance = MPGCalculator(data_dir)
    return _calculator_instance
