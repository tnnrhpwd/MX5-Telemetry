"""
MPG Calculator for MX5 Telemetry System

Calculates average fuel efficiency (MPG) and estimated range from CAN bus data.

Instantaneous MPG is NOT calculated here: it comes from mass air flow each loop
iteration and lives in instant_mpg.py. This module owns the two long-run gas
metrics, AVG MPG and RANGE.

TWO SOURCES, IN ORDER OF ACCURACY
---------------------------------
1. **Air flow (primary).** MAF is polled twice a second, and air mass converts to
   fuel mass with the same stoichiometric constants the instant reading uses
   (instant_mpg.py). Fuel used is simply summed over time, so idle and stop-start
   traffic are counted the way they are counted at a pump, and the average is
   right from the first mile. No dependence on the fuel sender.
2. **Fuel level (fallback).** Without MAF the only fuel signal left is the tank
   sender, which is coarse (~1% of 12.7 gal = 0.13 gal) and noisy. Distance is
   accumulated between level milestones and gallons are derived from the drop.

The air-flow total is used whenever it exists; the sender total is kept running
underneath so the readout survives a MAF drop-out without starting over, and so
the two can be compared in the journal.

Industry Standard Formulas:
- MPG = Distance (miles) / Fuel Used (gallons)
- Range = Remaining Fuel (gallons) x Average MPG

DATA SAFETY:
- Atomic writes (write to temp file, then rename) prevent corruption
- Backup file (.bak) preserves previous good state
- Load validates data and falls back to backup on failure
- Never overwrites good data with empty data (checks file on disk first)
- Startup fuel guard ignores fuel readings until CAN data stabilizes
"""

import json
import os
import time
import threading
from dataclasses import dataclass
from typing import Optional, List
from pathlib import Path

# The fuel model (stoichiometric AFR, gasoline density) is defined once, for both
# the instant reading and this long-run total. If those constants ever change, both
# numbers move together instead of drifting apart.
from instant_mpg import GALLONS_PER_HOUR_PER_GPS, MIN_MAF_GPS


@dataclass
class FuelMilestone:
    """Records a fuel consumption milestone"""
    fuel_pct: float          # Fuel level when recorded (0-100)
    total_distance: float    # Cumulative distance at this point
    timestamp: float         # Unix timestamp


class MPGCalculator:
    """
    Average fuel economy and range, from air flow first and the tank sender second.

    Strategy:
    1. Sum fuel from MAF every loop iteration (the accurate path)
    2. In parallel, track fuel-level milestones as a fallback and a cross-check
    3. Report distance/fuel from the best source that has enough data
    4. Persist both totals so a restart does not reset the tank average

    Data Safety:
    - Atomic writes prevent partial-write corruption
    - Backup file allows recovery from corruption
    - Refuses to overwrite higher-mileage data with empty/lower data
    - Startup fuel guard prevents false refuel detection from CAN init delay
    """

    # MX5 NC (2006-2015) tank capacity
    TANK_CAPACITY_GAL = 12.7

    # -- air-flow (MAF) accounting --
    #
    # Below this much summed fuel the average is not worth quoting. Air flow is a
    # precise measurement (2 Hz, no sender quantisation), so this is only about not
    # announcing a number from a handful of seconds; 0.05 gal is 0.4% of the tank,
    # about two minutes of driving.
    MIN_MAF_FUEL_FOR_AVERAGE = 0.05   # gallons
    # ...and it must cover at least this much running time, so one unusual moment
    # (a long downhill, say) cannot define the average.
    MIN_MAF_SECONDS_FOR_AVERAGE = 30.0

    # -- fuel-level (sender) accounting --

    # Minimum fuel drop to register a milestone (percentage points). 2% of the tank
    # is 0.25 gal; below that the sender's own noise dominates the measurement.
    FUEL_MILESTONE_THRESHOLD = 2.0

    # A rise this large means fuel went in. It used to be 10%, which meant a small
    # top-up was invisible: the milestone stayed above the new level, every later
    # drop read as negative, and the average silently stopped updating. 1% is just
    # above what a one-minute average of the sender drifts on its own.
    FUEL_RISE_DEADBAND = 1.0

    # Minimum distance between milestones (prevents noise at low speeds/idle)
    MIN_DISTANCE_FOR_MILESTONE = 1.0  # miles (increased from 0.5 to filter noise)
    
    # Minimum speed to count as driving (filters idle time)
    MIN_DRIVING_SPEED_MPH = 3.0
    
    # How often to save persistent data (seconds)
    SAVE_INTERVAL_SEC = 60.0
    
    # Rejection window for a single sender segment. A 2% drop over 1 mile can
    # legitimately be 8 mpg (a climb) or 60 mpg (a long coast), so this only weeds
    # out arithmetic that cannot be real - not merely bad economy.
    MAX_REASONABLE_MPG = 60.0
    MIN_REASONABLE_MPG = 8.0

    # Clamp on the *reported average*, wide enough never to flatter or punish a real
    # drive: this car does 15-35 mpg in normal use.
    AVERAGE_MAX_MPG = 60.0
    AVERAGE_MIN_MPG = 5.0
    
    # Number of recent MPG calculations to keep for rolling average
    MAX_RECENT_CALCULATIONS = 20
    
    # EPA default for MX5 NC (used when no data available at all)
    EPA_DEFAULT_MPG = 26.0
    
    # Startup fuel stabilization period — ignore fuel data for this many seconds
    # after startup to let CAN bus readings stabilize (prevents 0% → real% being
    # detected as a "refuel" event)
    FUEL_STABILIZE_SECONDS = 10.0
    
    def __init__(self, data_dir: str = "/home/pi/MX5-Telemetry/data",
                 verbose: bool = True):
        """
        Initialize MPG calculator.

        Args:
            data_dir: Directory for persistent data storage
            verbose: Print the periodic state line (tests switch it off)
        """
        self.data_dir = Path(data_dir)
        self.data_file = self.data_dir / "mpg_data.json"
        self.backup_file = self.data_dir / "mpg_data.json.bak"
        self.lock_file = self.data_dir / "mpg_data.lock"
        self._verbose = verbose
        
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
        
        # Lifetime totals from the fuel-level (sender) path, for persistence
        self._lifetime_miles = 0.0
        self._lifetime_gallons = 0.0

        # Air-flow (MAF) totals. Distance is counted only over the intervals where
        # the fuel flow was known, because the numerator and the denominator of an
        # average have to cover the same time or the number is meaningless: counting
        # miles we have no fuel figure for would inflate the average.
        self._maf_fuel_gal = 0.0
        self._maf_distance_mi = 0.0
        self._maf_seconds = 0.0
        self._maf_missing_seconds = 0.0   # engine running, no fresh MAF: for the log
        self._runtime_seconds = 0.0       # engine-on seconds this session

        # Which source produced the reported average: 'maf', 'fuel_gauge' or
        # 'estimated'. Exposed so a field diagnosis can tell a real number from the
        # EPA placeholder without reading the code.
        self._average_source = 'estimated'
        
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
              f"{self._lifetime_gallons:.2f} gal, avg MPG: {self._average_mpg:.1f} "
              f"({self._average_source})")
    
    def stop(self):
        """Stop the calculator and save data"""
        self._running = False
        self._save_data()
        print("MPG Calculator stopped and data saved.")
    
    # NOTE: there is deliberately no `instant_mpg` property here. Instantaneous fuel
    # economy is a MAF-derived value recomputed every loop iteration; it lives in
    # instant_mpg.py and is wired up in main.py. This class used to expose
    # `instant_mpg` as a property returning the *average*, which is the exact kind of
    # plausible-looking wrong number that ends up on a dash and never gets noticed.
    @property
    def average_mpg(self) -> float:
        """Get average MPG"""
        with self._lock:
            return self._average_mpg

    @property
    def average_mpg_source(self) -> str:
        """Where `average_mpg` came from: 'maf', 'fuel_gauge' or 'estimated'.

        'estimated' means no measurement exists yet and the EPA figure is being
        reported. UIs show the same number either way; this is for the log and the
        HTTP snapshot, so a surprising reading can be traced to its source.
        """
        with self._lock:
            return self._average_source
    
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
               engine_running: bool, dt_seconds: float = None,
               maf_gps: float = 0.0, maf_fresh: bool = False):
        """
        Update MPG calculations with latest CAN data.

        Args:
            speed_mph: Current vehicle speed in MPH
            raw_fuel_pct: Tank level percentage (0-100). Pass the *averaged* level,
                not the hysteresis-filtered one the screen shows: the deadband exists
                to stop the number twitching on the panel, and feeding it back into
                the arithmetic throws away up to 1.5% of every measurement.
            engine_running: True if engine is running (RPM > 0)
            dt_seconds: Time since last update (auto-calculated if None)
            maf_gps: Latest mass air flow sample in g/s (0 if none)
            maf_fresh: True when that sample is recent enough to integrate
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
        
        # Clamp dt to reasonable range (handles pauses/delays). This also bounds how
        # much distance or fuel a stalled iteration can invent.
        dt_seconds = min(dt_seconds, 1.0)
        self._last_update_time = current_time

        driving = engine_running and speed_mph >= self.MIN_DRIVING_SPEED_MPH
        distance_increment = (speed_mph / 3600.0) * dt_seconds if driving else 0.0

        # -- air-flow accounting: the accurate path -------------------------
        # Fuel is summed from metered air, so it needs no tank level, no milestone
        # and no waiting for a measurable drop. Distance is credited here only while
        # the fuel flow is known, because an average whose numerator and denominator
        # cover different intervals is not an average of anything.
        if engine_running:
            self._runtime_seconds += dt_seconds
            if maf_fresh and maf_gps >= MIN_MAF_GPS:
                self._maf_fuel_gal += (GALLONS_PER_HOUR_PER_GPS * maf_gps
                                       * (dt_seconds / 3600.0))
                self._maf_seconds += dt_seconds
                self._maf_distance_mi += distance_increment
            else:
                self._maf_missing_seconds += dt_seconds

        if distance_increment > 0:
            self._session_distance += distance_increment
            self._total_distance += distance_increment
            self._lifetime_miles += distance_increment

        # Validate fuel reading — treat 0% as uninitialized (CAN hasn't sent data yet)
        # Real fuel level will never be exactly 0.0% while engine is running.
        # `not (0 < x <= 100)` rather than `x <= 0 or x > 100` so a NaN frame fails
        # the test instead of propagating into every figure below.
        if not (0 < raw_fuel_pct <= 100):
            raw_fuel_pct = self._current_fuel_pct if self._current_fuel_pct > 0 else 0.0
            if raw_fuel_pct <= 0:
                # No tank reading yet. The air-flow average does not need one, so the
                # displays can still show a real MPG before the fuel frame appears.
                self._update_outputs(0.0)
                self._maybe_save(current_time)
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
                # Store fuel for display even before stabilized
                with self._lock:
                    self._current_fuel_pct = raw_fuel_pct
                self._update_outputs(raw_fuel_pct)
                self._maybe_save(current_time)
                return
        
        # Store current fuel for display
        with self._lock:
            self._current_fuel_pct = raw_fuel_pct
        
        # Initialize fuel tracking if needed (only after stabilization)
        if self._last_fuel_pct is None or self._last_fuel_pct <= 0:
            self._last_fuel_pct = raw_fuel_pct
            self._fuel_at_milestone = raw_fuel_pct
            print(f"MPG: Initialized fuel tracking at {raw_fuel_pct:.1f}%")

        self._track_fuel_level(raw_fuel_pct)

        self._last_fuel_pct = raw_fuel_pct
        
        # Update output values
        self._update_outputs(raw_fuel_pct)
        self._maybe_save(current_time)
        
        # Debug output periodically
        self._debug_counter += 1
        if self._verbose and self._debug_counter >= 300:  # Every ~10 seconds at 30Hz
            self._debug_counter = 0
            if engine_running:
                print(f"MPG DEBUG: fuel={raw_fuel_pct:.1f}%, session_dist={self._session_distance:.2f}mi, "
                      f"avg={self._average_mpg:.1f} ({self._average_source}), "
                      f"range={self._range_miles}mi, "
                      f"maf={self._maf_fuel_gal:.2f}gal/{self._maf_distance_mi:.1f}mi, "
                      f"milestone_fuel={self._fuel_at_milestone:.1f}%, "
                      f"lifetime={self._lifetime_miles:.1f}mi")

    # -- fuel-level accounting ---------------------------------------------

    def _track_fuel_level(self, fuel_pct: float):
        """Sender-based fuel accounting: the fallback and the cross-check.

        Two things move the segment boundary: the level fell by a milestone's worth
        (fuel was burned), or it rose (fuel was added). Only the first used to be
        handled, and only a rise of 10% or more counted as a fill - so an ordinary
        top-up left the milestone stranded above the new level, every later drop read
        as negative, and the average quietly stopped updating until the tank went
        below the old mark.
        """
        if not self._fuel_at_milestone or self._fuel_at_milestone <= 0:
            self._fuel_at_milestone = fuel_pct
            return

        drop = self._fuel_at_milestone - fuel_pct
        rise = fuel_pct - self._fuel_at_milestone

        if drop >= self.FUEL_MILESTONE_THRESHOLD:
            gallons_used = (drop / 100.0) * self.TANK_CAPACITY_GAL

            # The fuel was burned whether or not there is a distance to divide it
            # by, so it always counts toward the lifetime total. It used to count
            # only when a sample was accepted, which silently dropped every idling,
            # warming-up or crawling stretch out of the denominator and biased the
            # average upward - the error this method is least able to afford.
            self._lifetime_gallons += gallons_used

            if self._session_distance >= self.MIN_DISTANCE_FOR_MILESTONE:
                segment_mpg = self._session_distance / gallons_used if gallons_used > 0 else 0.0
                if self.MIN_REASONABLE_MPG <= segment_mpg <= self.MAX_REASONABLE_MPG:
                    self._record_recent(segment_mpg, self._session_distance)
                    print(f"MPG: Milestone! Fuel {self._fuel_at_milestone:.1f}% -> {fuel_pct:.1f}% "
                          f"({drop:.1f}% drop = {gallons_used:.2f}gal), "
                          f"distance: {self._session_distance:.1f}mi, MPG: {segment_mpg:.1f}, "
                          f"lifetime: {self._lifetime_miles:.1f}mi / {self._lifetime_gallons:.2f}gal")
                else:
                    print(f"MPG: Milestone with an implausible MPG: {segment_mpg:.1f} "
                          f"(fuel drop {drop:.1f}% = {gallons_used:.2f}gal over "
                          f"{self._session_distance:.1f}mi). Gallons still counted.")
            else:
                # Burned while parked or crawling: real fuel, no distance to divide
                # by, so there is no sample to quote - but the gallons above are
                # exactly what makes a stop-start drive read honestly.
                print(f"MPG: Burned {gallons_used:.2f}gal ({drop:.1f}%) with only "
                      f"{self._session_distance:.2f}mi covered. Gallons counted, "
                      f"no MPG sample.")

            self._fuel_at_milestone = fuel_pct
            self._session_distance = 0.0
            return

        if rise >= self.FUEL_RISE_DEADBAND:
            self._count_tail_to_fill(fuel_pct, rise)
            self._fuel_at_milestone = fuel_pct
            self._session_distance = 0.0

    def _count_tail_to_fill(self, fuel_pct: float, rise: float):
        """Count the fuel burned between the last milestone and the fill-up.

        Without this the last slice of every tank (last milestone -> pump) is never
        counted, which is the single largest way to undercount gallons and inflate
        the average over a few tanks.
        """
        last = self._last_fuel_pct
        if not last or last <= 0 or not self._fuel_at_milestone:
            print(f"MPG: Fuel added ({fuel_pct:.1f}%, +{rise:.1f}%) with no prior level")
            return

        tail_drop = self._fuel_at_milestone - last
        if tail_drop <= 0:
            print(f"MPG: Fuel added {self._fuel_at_milestone:.1f}% -> {fuel_pct:.1f}% "
                  f"(+{rise:.1f}%, no tail to count)")
            return

        tail_gallons = (tail_drop / 100.0) * self.TANK_CAPACITY_GAL
        self._lifetime_gallons += tail_gallons

        if self._session_distance >= self.MIN_DISTANCE_FOR_MILESTONE and tail_gallons > 0:
            tail_mpg = self._session_distance / tail_gallons
            if self.MIN_REASONABLE_MPG <= tail_mpg <= self.MAX_REASONABLE_MPG:
                self._record_recent(tail_mpg, self._session_distance)

        print(f"MPG: Fuel added {self._fuel_at_milestone:.1f}% -> {fuel_pct:.1f}% (+{rise:.1f}%). "
              f"Counted tail {self._fuel_at_milestone:.1f}% -> {last:.1f}% "
              f"= {tail_gallons:.3f}gal over {self._session_distance:.1f}mi. "
              f"Lifetime: {self._lifetime_miles:.1f}mi / {self._lifetime_gallons:.2f}gal")

    def _record_recent(self, mpg: float, distance: float):
        """Keep the last few sender-derived samples for a responsive blend."""
        self._recent_mpg_values.append(mpg)
        self._recent_distances.append(distance)
        while len(self._recent_mpg_values) > self.MAX_RECENT_CALCULATIONS:
            self._recent_mpg_values.pop(0)
            self._recent_distances.pop(0)

    def _maybe_save(self, now: float):
        if now - self._last_save_time >= self.SAVE_INTERVAL_SEC:
            self._save_data()
            self._last_save_time = now
    
    def _update_outputs(self, raw_fuel_pct: float):
        """Recompute the reported average and the range it implies."""
        with self._lock:
            self._average_mpg, self._average_source = self._choose_average()

            # Range = remaining fuel x average. Only meaningful with a tank reading;
            # 0 is reported otherwise and the UIs draw "--".
            if 0 < raw_fuel_pct <= 100:
                remaining_gal = (raw_fuel_pct / 100.0) * self.TANK_CAPACITY_GAL
                self._range_miles = int(remaining_gal * self._average_mpg)
            else:
                self._range_miles = 0

    def _choose_average(self):
        """Return (mpg, source), best source first.

        Air flow wins whenever it has enough coverage, because it measures fuel
        rather than inferring it from a sender with 0.13 gal steps. The sender total
        still takes over when air flow is missing for a long stretch, so a MAF
        failure degrades the number instead of freezing it.
        """
        maf_usable = (self._maf_fuel_gal >= self.MIN_MAF_FUEL_FOR_AVERAGE and
                      self._maf_seconds >= self.MIN_MAF_SECONDS_FOR_AVERAGE)

        # More than ten minutes and more than half the session spent with no air
        # flow means the MAF path no longer describes what the car is doing.
        if maf_usable and self._maf_missing_seconds > 600.0 and \
                self._maf_missing_seconds > 0.5 * self._runtime_seconds:
            maf_usable = False

        if maf_usable:
            return self._clamp_average(self._maf_distance_mi / self._maf_fuel_gal), 'maf'

        if self._lifetime_gallons > 0.5:
            # Enough sender data — mostly lifetime, with a little recent for
            # responsiveness to how the car is being driven now.
            lifetime_mpg = self._lifetime_miles / self._lifetime_gallons
            recent_mpg = self._weighted_recent_mpg()
            if recent_mpg is not None:
                return self._clamp_average(0.8 * lifetime_mpg + 0.2 * recent_mpg), 'fuel_gauge'
            return self._clamp_average(lifetime_mpg), 'fuel_gauge'

        if self._lifetime_gallons > 0.1:
            # Some lifetime data — use it directly
            return self._clamp_average(
                self._lifetime_miles / self._lifetime_gallons), 'fuel_gauge'

        recent_mpg = self._weighted_recent_mpg()
        if recent_mpg is not None:
            return self._clamp_average(recent_mpg), 'fuel_gauge'

        # Nothing measured yet. 26 mpg is the EPA figure for this car, not a
        # measurement, which is why the source is reported alongside it.
        return self.EPA_DEFAULT_MPG, 'estimated'

    def _weighted_recent_mpg(self) -> Optional[float]:
        """Distance-weighted mean of the recent sender segments, or None."""
        if not self._recent_mpg_values or not self._recent_distances:
            return None
        total_dist = sum(self._recent_distances)
        if total_dist <= 0:
            return None
        weighted_sum = sum(m * d for m, d in
                           zip(self._recent_mpg_values, self._recent_distances))
        return weighted_sum / total_dist

    def _clamp_average(self, mpg: float) -> float:
        return max(self.AVERAGE_MIN_MPG, min(mpg, self.AVERAGE_MAX_MPG))
    
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

            # Air-flow totals (absent in files written before they existed)
            self._maf_fuel_gal = max(0.0, data.get('maf_fuel_gal', 0.0))
            self._maf_distance_mi = max(0.0, data.get('maf_distance_mi', 0.0))
            self._maf_seconds = max(0.0, data.get('maf_seconds', 0.0))

            # Calculate the initial average from whatever survived validation
            self._average_mpg, self._average_source = self._choose_average()

            print(f"MPG: Loaded from {source} — {len(self._recent_mpg_values)} recent calculations, "
                  f"lifetime: {self._lifetime_miles:.1f}mi / {self._lifetime_gallons:.2f}gal, "
                  f"air flow: {self._maf_distance_mi:.1f}mi / {self._maf_fuel_gal:.2f}gal, "
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
                'maf_fuel_gal': self._maf_fuel_gal,
                'maf_distance_mi': self._maf_distance_mi,
                'maf_seconds': self._maf_seconds,
                'recent_mpg_values': self._recent_mpg_values,
                'recent_distances': self._recent_distances,
                'fuel_at_milestone': self._fuel_at_milestone,
                'session_distance': self._session_distance,
                'last_fuel_pct': self._last_fuel_pct,
                'last_save_time': time.time(),
                'calculated_avg_mpg': self._average_mpg,
                'average_source': self._average_source,
                '_comment': 'MPG data for MX5 Telemetry. Air-flow totals first, '
                            'fuel-level milestones as the fallback.'
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
        self._maf_fuel_gal = 0.0
        self._maf_distance_mi = 0.0
        self._maf_seconds = 0.0
        self._maf_missing_seconds = 0.0
        self._runtime_seconds = 0.0
        self._recent_mpg_values = []
        self._recent_distances = []
        self._fuel_at_milestone = None
        self._session_distance = 0.0
        self._average_mpg = self.EPA_DEFAULT_MPG
        self._average_source = 'estimated'
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
