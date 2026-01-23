"""
MPG Calculator for MX5 Telemetry System

Calculates fuel efficiency (MPG) and estimated range from CAN bus data.
Implements fuel smoothing to handle sensor noise and tank sloshing.

Design Principles:
- Exponential Moving Average (EMA) for fuel level smoothing
- Trip-based tracking with persistent lifetime statistics
- Integration-based distance calculation from speed
- JSON persistence for data survival across restarts

Industry Standard Formulas:
- MPG = Distance (miles) / Fuel Used (gallons)
- Range = Remaining Fuel (gallons) × Average MPG
- EMA: smoothed = α × current + (1-α) × previous
"""

import json
import os
import time
import threading
from dataclasses import dataclass, asdict
from typing import Optional
from pathlib import Path


@dataclass
class TripData:
    """Data for current driving trip (resets on engine start)"""
    start_time: float = 0.0
    start_fuel_pct: float = 0.0
    distance_miles: float = 0.0
    fuel_used_gal: float = 0.0
    
    @property
    def mpg(self) -> float:
        """Calculate trip MPG"""
        if self.fuel_used_gal > 0.001:  # Lowered threshold for faster display
            return self.distance_miles / self.fuel_used_gal
        return 0.0


@dataclass
class LifetimeData:
    """Persistent lifetime statistics"""
    total_miles: float = 0.0
    total_gallons: float = 0.0
    last_fuel_pct: float = 0.0
    last_odometer: float = 0.0
    samples_count: int = 0
    
    # Rolling average buffer (last N trip MPGs for weighted average)
    recent_trip_mpgs: list = None
    recent_trip_distances: list = None
    
    def __post_init__(self):
        if self.recent_trip_mpgs is None:
            self.recent_trip_mpgs = []
        if self.recent_trip_distances is None:
            self.recent_trip_distances = []
    
    @property
    def average_mpg(self) -> float:
        """Calculate lifetime average MPG"""
        if self.total_gallons > 0.01:  # Lowered from 0.1 for faster display
            return self.total_miles / self.total_gallons
        # Fall back to recent trips weighted average
        if self.recent_trip_distances and sum(self.recent_trip_distances) > 0:
            total_dist = sum(self.recent_trip_distances)
            weighted_sum = sum(mpg * dist for mpg, dist in 
                             zip(self.recent_trip_mpgs, self.recent_trip_distances))
            return weighted_sum / total_dist
        return 26.0  # Return EPA default instead of 0 so display shows something


class MPGCalculator:
    """
    Calculates MPG and estimated range from CAN data.
    
    Strategy:
    1. Smooth fuel level with EMA to filter sensor noise
    2. Track distance traveled (integrated from speed)
    3. Track fuel consumed (delta from smoothed readings)
    4. Persist statistics to JSON for long-term accuracy
    5. Calculate range from remaining fuel × average MPG
    
    Usage:
        calculator = MPGCalculator()
        calculator.start()
        
        # In main loop:
        calculator.update(speed_mph, raw_fuel_pct, engine_running, dt)
        
        # Read outputs:
        print(f"Average MPG: {calculator.average_mpg}")
        print(f"Range: {calculator.range_miles} miles")
    """
    
    # MX5 NC (2006-2015) tank capacity
    TANK_CAPACITY_GAL = 12.7
    
    # Fuel EMA smoothing factor
    # Lower = smoother but slower response
    # 0.05 means ~20 samples (0.7 sec at 30Hz) to reach 63% of step change
    FUEL_EMA_ALPHA = 0.05  # Increased from 0.02 for faster response
    
    # Minimum speed to consider "driving" (avoids noise at idle)
    MIN_DRIVING_SPEED_MPH = 3.0
    
    # Minimum fuel change to register (filters sensor noise)
    MIN_FUEL_CHANGE_PCT = 0.1
    
    # How often to save persistent data (seconds)
    SAVE_INTERVAL_SEC = 60.0
    
    # Maximum reasonable MPG (sanity check)
    MAX_REASONABLE_MPG = 50.0
    
    # Number of recent trips to keep for rolling average
    MAX_RECENT_TRIPS = 20
    
    def __init__(self, data_dir: str = "/home/pi/MX5-Telemetry/data"):
        """
        Initialize MPG calculator.
        
        Args:
            data_dir: Directory for persistent data storage
        """
        self.data_dir = Path(data_dir)
        self.data_file = self.data_dir / "mpg_data.json"
        
        # Current trip data
        self.trip = TripData()
        
        # Lifetime persistent data
        self.lifetime = LifetimeData()
        
        # Smoothed fuel level (EMA filtered)
        self._smoothed_fuel_pct: Optional[float] = None
        self._prev_smoothed_fuel_pct: Optional[float] = None
        
        # State tracking
        self._engine_was_running = False
        self._last_update_time = 0.0
        self._last_save_time = 0.0
        self._trip_active = False
        
        # Output values (thread-safe reads)
        self._lock = threading.Lock()
        self._instant_mpg = 0.0
        self._average_mpg = 0.0
        self._range_miles = 0
        self._smoothed_fuel_display = 0.0
        
        # Instant MPG calculation buffer
        self._instant_distance_buffer = 0.0
        self._instant_fuel_buffer = 0.0
        self._instant_calc_interval = 5.0  # Calculate instant MPG every 5 seconds
        self._last_instant_calc_time = 0.0
        
        # Running flag
        self._running = False
    
    def start(self):
        """Start the calculator and load persistent data"""
        self._running = True
        self._load_data()
        
        # Initialize outputs to reasonable defaults immediately
        # This ensures MPG/range display something before engine starts
        with self._lock:
            self._average_mpg = self.lifetime.average_mpg
            if self._average_mpg <= 0:
                self._average_mpg = 26.0  # EPA default
        
        print(f"MPG Calculator started. Lifetime: {self.lifetime.total_miles:.1f} mi, "
              f"{self.lifetime.total_gallons:.2f} gal, avg {self.lifetime.average_mpg:.1f} MPG")
    
    def stop(self):
        """Stop the calculator and save data"""
        self._running = False
        self._end_trip()
        self._save_data()
        print("MPG Calculator stopped and data saved.")
    
    @property
    def instant_mpg(self) -> float:
        """Get instantaneous MPG (short-term calculation)"""
        with self._lock:
            return self._instant_mpg
    
    @property
    def average_mpg(self) -> float:
        """Get average MPG (lifetime or recent trips)"""
        with self._lock:
            return self._average_mpg
    
    @property
    def range_miles(self) -> int:
        """Get estimated range in miles"""
        with self._lock:
            return self._range_miles
    
    @property
    def smoothed_fuel_pct(self) -> float:
        """Get smoothed fuel percentage"""
        with self._lock:
            return self._smoothed_fuel_display
    
    @property
    def trip_mpg(self) -> float:
        """Get current trip MPG"""
        return self.trip.mpg
    
    @property
    def trip_distance(self) -> float:
        """Get current trip distance in miles"""
        return self.trip.distance_miles
    
    def update(self, speed_mph: float, raw_fuel_pct: float, 
               engine_running: bool, dt_seconds: float = None):
        """
        Update MPG calculations with latest CAN data.
        
        Should be called at regular intervals (e.g., 30Hz from main loop).
        
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
        
        # Detect engine start/stop
        if engine_running and not self._engine_was_running:
            self._start_trip(raw_fuel_pct)
        elif not engine_running and self._engine_was_running:
            self._end_trip()
        
        self._engine_was_running = engine_running
        
        # Always update smoothed fuel and outputs (even when engine off)
        # This ensures the fuel gauge and range display work while parked
        self._update_fuel_ema(raw_fuel_pct)
        
        # Only process distance/fuel consumption if engine is running
        if engine_running and speed_mph >= self.MIN_DRIVING_SPEED_MPH and self._trip_active:
            # Accumulate distance
            distance_increment = (speed_mph / 3600.0) * dt_seconds  # miles
            self.trip.distance_miles += distance_increment
            self._instant_distance_buffer += distance_increment
            
            # Calculate fuel consumption from smoothed fuel delta
            if self._prev_smoothed_fuel_pct is not None and self._smoothed_fuel_pct is not None:
                fuel_delta_pct = self._prev_smoothed_fuel_pct - self._smoothed_fuel_pct
                
                # Only count positive fuel consumption (ignore refueling)
                if fuel_delta_pct > 0:
                    fuel_delta_gal = (fuel_delta_pct / 100.0) * self.TANK_CAPACITY_GAL
                    self.trip.fuel_used_gal += fuel_delta_gal
                    self._instant_fuel_buffer += fuel_delta_gal
                    
                    # Also accumulate to lifetime (will be persisted)
                    self.lifetime.total_miles += distance_increment
                    self.lifetime.total_gallons += fuel_delta_gal
        
        # Store previous smoothed value for next delta calculation
        self._prev_smoothed_fuel_pct = self._smoothed_fuel_pct
        
        # Calculate instant MPG periodically (only when engine running)
        if engine_running and current_time - self._last_instant_calc_time >= self._instant_calc_interval:
            self._calculate_instant_mpg()
            self._last_instant_calc_time = current_time
        
        # Update output values (pass raw fuel for fallback range calculation)
        self._update_outputs(raw_fuel_pct)
        
        # Periodic save
        if current_time - self._last_save_time >= self.SAVE_INTERVAL_SEC:
            self._save_data()
            self._last_save_time = current_time
    
    def _update_fuel_ema(self, raw_fuel_pct: float):
        """Apply Exponential Moving Average to fuel level"""
        if raw_fuel_pct < 0 or raw_fuel_pct > 100:
            return  # Invalid reading
        
        if self._smoothed_fuel_pct is None:
            # Initialize on first reading
            self._smoothed_fuel_pct = raw_fuel_pct
        else:
            # EMA formula: new = α * current + (1-α) * previous
            self._smoothed_fuel_pct = (
                self.FUEL_EMA_ALPHA * raw_fuel_pct + 
                (1 - self.FUEL_EMA_ALPHA) * self._smoothed_fuel_pct
            )
    
    def _calculate_instant_mpg(self):
        """Calculate instantaneous MPG from recent buffer"""
        if self._instant_fuel_buffer > 0.001:  # Minimum fuel to calculate
            instant = self._instant_distance_buffer / self._instant_fuel_buffer
            # Sanity check
            if 0 < instant <= self.MAX_REASONABLE_MPG:
                with self._lock:
                    self._instant_mpg = instant
        
        # Reset buffers
        self._instant_distance_buffer = 0.0
        self._instant_fuel_buffer = 0.0
    
    def _update_outputs(self, raw_fuel_pct: float = None):
        """Update thread-safe output values
        
        Args:
            raw_fuel_pct: Optional raw fuel percentage for fallback calculation
        """
        with self._lock:
            # Average MPG from lifetime data
            self._average_mpg = self.lifetime.average_mpg
            
            # If no lifetime data yet, use trip MPG
            if self._average_mpg <= 0 and self.trip.mpg > 0:
                self._average_mpg = self.trip.mpg
            
            # Default to reasonable MX5 average if no data
            if self._average_mpg <= 0:
                self._average_mpg = 26.0  # EPA combined for MX5 NC
            
            # Clamp to reasonable range
            self._average_mpg = min(self._average_mpg, self.MAX_REASONABLE_MPG)
            
            # Calculate range - prefer smoothed fuel, fallback to raw fuel
            fuel_pct = self._smoothed_fuel_pct
            if fuel_pct is None and raw_fuel_pct is not None and raw_fuel_pct > 0:
                fuel_pct = raw_fuel_pct
            
            if fuel_pct is not None and fuel_pct > 0:
                remaining_gal = (fuel_pct / 100.0) * self.TANK_CAPACITY_GAL
                self._range_miles = int(remaining_gal * self._average_mpg)
            
            # Update smoothed fuel for display
            if self._smoothed_fuel_pct is not None:
                self._smoothed_fuel_display = self._smoothed_fuel_pct
            elif raw_fuel_pct is not None:
                self._smoothed_fuel_display = raw_fuel_pct
    
    def _start_trip(self, initial_fuel_pct: float):
        """Start a new trip when engine starts"""
        print(f"MPG: Starting new trip at {initial_fuel_pct:.1f}% fuel")
        
        self.trip = TripData(
            start_time=time.time(),
            start_fuel_pct=initial_fuel_pct,
            distance_miles=0.0,
            fuel_used_gal=0.0
        )
        
        # Initialize smoothed fuel
        self._smoothed_fuel_pct = initial_fuel_pct
        self._prev_smoothed_fuel_pct = initial_fuel_pct
        
        self._trip_active = True
        self._instant_distance_buffer = 0.0
        self._instant_fuel_buffer = 0.0
    
    def _end_trip(self):
        """End current trip and record statistics"""
        if not self._trip_active:
            return
        
        self._trip_active = False
        
        # Only record meaningful trips (> 0.5 miles, > 0.01 gallons)
        if self.trip.distance_miles > 0.5 and self.trip.fuel_used_gal > 0.01:
            trip_mpg = self.trip.mpg
            
            # Sanity check
            if 5.0 <= trip_mpg <= self.MAX_REASONABLE_MPG:
                # Add to recent trips for rolling average
                self.lifetime.recent_trip_mpgs.append(trip_mpg)
                self.lifetime.recent_trip_distances.append(self.trip.distance_miles)
                
                # Trim to max size
                while len(self.lifetime.recent_trip_mpgs) > self.MAX_RECENT_TRIPS:
                    self.lifetime.recent_trip_mpgs.pop(0)
                    self.lifetime.recent_trip_distances.pop(0)
                
                print(f"MPG: Trip ended - {self.trip.distance_miles:.1f} mi, "
                      f"{self.trip.fuel_used_gal:.2f} gal, {trip_mpg:.1f} MPG")
                
                # Save immediately after trip ends
                self._save_data()
    
    def _load_data(self):
        """Load persistent data from JSON file"""
        try:
            if self.data_file.exists():
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                
                # Restore lifetime data
                self.lifetime.total_miles = data.get('total_miles', 0.0)
                self.lifetime.total_gallons = data.get('total_gallons', 0.0)
                self.lifetime.last_fuel_pct = data.get('last_fuel_pct', 0.0)
                self.lifetime.samples_count = data.get('samples_count', 0)
                self.lifetime.recent_trip_mpgs = data.get('recent_trip_mpgs', [])
                self.lifetime.recent_trip_distances = data.get('recent_trip_distances', [])
                
                # Validate and fix corrupted data
                if self.lifetime.total_miles < 0:
                    print(f"MPG: Fixing negative total_miles: {self.lifetime.total_miles}")
                    self.lifetime.total_miles = 0.0
                if self.lifetime.total_gallons < 0:
                    print(f"MPG: Fixing negative total_gallons: {self.lifetime.total_gallons}")
                    self.lifetime.total_gallons = 0.0
                
                # Check for unreasonable MPG (would indicate bad data)
                if self.lifetime.total_gallons > 0:
                    calculated_mpg = self.lifetime.total_miles / self.lifetime.total_gallons
                    if calculated_mpg > 100 or calculated_mpg < 5:
                        print(f"MPG: Data appears corrupted (calculated MPG: {calculated_mpg:.1f})")
                        print(f"  total_miles={self.lifetime.total_miles}, total_gallons={self.lifetime.total_gallons}")
                        # Keep the data but it will fall back to recent trips or EPA default
                
                print(f"MPG: Loaded data - {self.lifetime.total_miles:.1f} mi total, "
                      f"{len(self.lifetime.recent_trip_mpgs)} recent trips, "
                      f"avg {self.lifetime.average_mpg:.1f} MPG")
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
                'total_miles': self.lifetime.total_miles,
                'total_gallons': self.lifetime.total_gallons,
                'last_fuel_pct': self._smoothed_fuel_pct or 0.0,
                'samples_count': self.lifetime.samples_count,
                'recent_trip_mpgs': self.lifetime.recent_trip_mpgs,
                'recent_trip_distances': self.lifetime.recent_trip_distances,
                'last_save_time': time.time(),
                'average_mpg': self.lifetime.average_mpg
            }
            
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            print(f"MPG: Error saving data: {e}")
    
    def reset_lifetime_data(self):
        """Reset all lifetime statistics (use with caution)"""
        print("MPG: Resetting lifetime data")
        self.lifetime = LifetimeData()
        self._save_data()
    
    def reset_trip(self):
        """Reset current trip data"""
        if self._smoothed_fuel_pct is not None:
            self._start_trip(self._smoothed_fuel_pct)


# Singleton instance for easy import
_calculator_instance: Optional[MPGCalculator] = None


def get_mpg_calculator(data_dir: str = "/home/pi/MX5-Telemetry/data") -> MPGCalculator:
    """Get or create the global MPG calculator instance"""
    global _calculator_instance
    if _calculator_instance is None:
        _calculator_instance = MPGCalculator(data_dir)
    return _calculator_instance
