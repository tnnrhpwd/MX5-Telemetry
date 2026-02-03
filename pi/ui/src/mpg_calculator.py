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
"""

import json
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
    """
    
    # MX5 NC (2006-2015) tank capacity
    TANK_CAPACITY_GAL = 12.7
    
    # Minimum fuel drop to register a milestone (percentage points)
    # Fuel sensors typically have 1-2% resolution, so 1% is reasonable
    FUEL_MILESTONE_THRESHOLD = 1.0
    
    # Minimum distance between milestones (prevents noise at low speeds/idle)
    MIN_DISTANCE_FOR_MILESTONE = 0.5  # miles
    
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
    
    def __init__(self, data_dir: str = "/home/pi/MX5-Telemetry/data"):
        """
        Initialize MPG calculator.
        
        Args:
            data_dir: Directory for persistent data storage
        """
        self.data_dir = Path(data_dir)
        self.data_file = self.data_dir / "mpg_data.json"
        
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
        
        # Validate fuel reading
        if raw_fuel_pct < 0 or raw_fuel_pct > 100:
            raw_fuel_pct = self._current_fuel_pct  # Use last known good value
        
        # Store current fuel for display
        with self._lock:
            self._current_fuel_pct = raw_fuel_pct
        
        # Initialize fuel tracking if needed
        if self._last_fuel_pct is None:
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
                      f"distance: {self._session_distance:.1f}mi, MPG: {segment_mpg:.1f}")
            else:
                print(f"MPG: Skipping unreasonable MPG: {segment_mpg:.1f} "
                      f"(fuel drop {fuel_drop:.1f}%, distance {self._session_distance:.1f}mi)")
            
            # Reset for next segment
            self._fuel_at_milestone = raw_fuel_pct
            self._session_distance = 0.0
        
        # Detect refueling (fuel increased significantly)
        if raw_fuel_pct > self._last_fuel_pct + 5.0:  # 5% increase = likely refueled
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
                      f"milestone_fuel={self._fuel_at_milestone:.1f}%")
    
    def _update_outputs(self, raw_fuel_pct: float):
        """Update thread-safe output values"""
        with self._lock:
            # Calculate average MPG from recent values (distance-weighted)
            if self._recent_mpg_values and self._recent_distances:
                total_dist = sum(self._recent_distances)
                if total_dist > 0:
                    weighted_sum = sum(mpg * dist for mpg, dist in 
                                     zip(self._recent_mpg_values, self._recent_distances))
                    self._average_mpg = weighted_sum / total_dist
            elif self._lifetime_gallons > 0.1:
                # Fall back to lifetime average
                self._average_mpg = self._lifetime_miles / self._lifetime_gallons
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
        """Load persistent data from JSON file"""
        try:
            if self.data_file.exists():
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                
                # Restore data
                self._lifetime_miles = max(0, data.get('total_miles', 0.0))
                self._lifetime_gallons = max(0, data.get('total_gallons', 0.0))
                self._recent_mpg_values = data.get('recent_mpg_values', [])
                self._recent_distances = data.get('recent_distances', [])
                self._fuel_at_milestone = data.get('fuel_at_milestone', None)
                
                # Validate loaded MPG values
                valid_mpgs = []
                valid_dists = []
                for mpg, dist in zip(self._recent_mpg_values, self._recent_distances):
                    if self.MIN_REASONABLE_MPG <= mpg <= self.MAX_REASONABLE_MPG and dist > 0:
                        valid_mpgs.append(mpg)
                        valid_dists.append(dist)
                self._recent_mpg_values = valid_mpgs
                self._recent_distances = valid_dists
                
                # Calculate initial average
                if self._recent_distances and sum(self._recent_distances) > 0:
                    total_dist = sum(self._recent_distances)
                    weighted_sum = sum(m * d for m, d in zip(self._recent_mpg_values, self._recent_distances))
                    self._average_mpg = weighted_sum / total_dist
                elif self._lifetime_gallons > 0.1:
                    self._average_mpg = self._lifetime_miles / self._lifetime_gallons
                
                print(f"MPG: Loaded {len(self._recent_mpg_values)} recent calculations, "
                      f"lifetime: {self._lifetime_miles:.1f}mi / {self._lifetime_gallons:.2f}gal")
            else:
                print("MPG: No existing data file, starting fresh")
                
        except Exception as e:
            print(f"MPG: Error loading data: {e}")
    
    def _save_data(self):
        """Save persistent data to JSON file"""
        try:
            # Ensure directory exists
            self.data_dir.mkdir(parents=True, exist_ok=True)
            
            data = {
                'total_miles': self._lifetime_miles,
                'total_gallons': self._lifetime_gallons,
                'recent_mpg_values': self._recent_mpg_values,
                'recent_distances': self._recent_distances,
                'fuel_at_milestone': self._fuel_at_milestone,
                'last_save_time': time.time(),
                'calculated_avg_mpg': self._average_mpg,
                '_comment': 'MPG data for MX5 Telemetry. Uses milestone-based tracking.'
            }
            
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)
                
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
