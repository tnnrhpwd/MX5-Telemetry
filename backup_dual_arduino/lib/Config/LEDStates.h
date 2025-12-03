#ifndef LED_STATES_H
#define LED_STATES_H

// ============================================================================
// LED Strip State Definitions - Mirrored Progress Bar System
// ============================================================================
// This file defines the LED strip states with a mirrored progress bar.
// These constants are shared between the Arduino code and Python simulator.
// LED state is now PURELY RPM-based - speed has no effect on LED display.
// ============================================================================
// 
// 🎨 STATE 0: IDLE/NEUTRAL - DEPRECATED (no longer used)
// -------------------------------------------------
// Previously triggered when speed = 0. Now LED display is purely RPM-based
// so you can see the proper RPM feedback when idling/revving while stationary.
// The idle animation code remains for potential future use.
//
// 🎨 STATE 1: GAS EFFICIENCY ZONE (Optimal Cruising)
// ---------------------------------------------------
// Visual: Gentle steady green glow on outermost 2 LEDs per side
// Purpose: Quiet confirmation of optimal cruising range
// Pattern: 🟢 🟢 ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ 🟢 🟢
//
// 🎨 STATE 2: STALL DANGER (Very Low RPM)
// ----------------------------------------
// Visual: Orange bars pulse outward from center to edges
// Purpose: Warning that engine is operating below torque/lugging
// Pattern: ⚫ ⚫ ⚫ 🟠 🟠 ⚫ ⚫ 🟠 🟠 ⚫ ⚫ ⚫ → 🟠 🟠 🟠 🟠 🟠 🟠 🟠 🟠
//
// 🎨 STATE 3: NORMAL DRIVING / POWER BAND
// ----------------------------------------
// Visual: Yellow bars grow inward from edges toward center
// Purpose: Mirrored progress bar showing current RPM percentage
// Pattern: 🟡 🟡 🟡 🟡 🟡 ⚫ ⚫ ⚫ ⚫ 🟡 🟡 🟡 🟡 🟡
//
// 🎨 STATE 4: HIGH RPM / SHIFT DANGER (Flashing Gap)
// ---------------------------------------------------
// Visual: Red bars continue inward, unfilled center gap flashes red/white
// Purpose: Urgent warning to shift before bars meet
// Pattern: 🟥 🟥 🟥 🟥 🟥 🟥 ✨ ✨ ✨ ✨ 🟥 🟥 🟥 🟥 🟥 🟥
//
// 🎨 STATE 5: REV LIMIT CUT (Full Strip)
// ---------------------------------------
// Visual: Complete solid red strip (bars have met)
// Purpose: Maximum limit reached, fuel cut engaged
// Pattern: 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥
//
// 🎨 ERROR STATE: CAN BUS READ ERROR
// -----------------------------------
// Visual: Red LEDs sequentially pepper inward from edges to center
// Purpose: Indicates RPM data communication failure
// Pattern: 🔴 ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ → 🔴 🔴 ⚫ ⚫ ⚫ ⚫ 🔴 🔴
// ============================================================================

// ============================================================================
// State 0: Idle/Neutral (Vehicle Not Moving, RPM 0-2000)
// Progressive white inward bar - more LEDs as RPM increases
// Always shows at least 1 LED per side even at RPM=0
// ============================================================================
#define STATE_0_SPEED_THRESHOLD 1        // Speed <= 1 km/h triggers this state

// Animation parameters (kept for backward compatibility)
#define STATE_0_PEPPER_DELAY    80       // Milliseconds between each LED lighting
#define STATE_0_HOLD_TIME       300      // Milliseconds to hold full pattern before repeating

// Color definition (White)
#define STATE_0_COLOR_R         255
#define STATE_0_COLOR_G         255
#define STATE_0_COLOR_B         255
#define STATE_0_BRIGHTNESS      180

// ============================================================================
// State 1: Gas Efficiency Zone (Optimal Cruising)
// ============================================================================
#define STATE_1_RPM_MIN         2000     // Minimum RPM for State 1
#define STATE_1_RPM_MAX         2500     // Maximum RPM for State 1

// Visual: Outermost 2 LEDs per side
#define STATE_1_LEDS_PER_SIDE   2        // Number of LEDs lit on each edge

// Color definition (Green)
#define STATE_1_COLOR_R         0
#define STATE_1_COLOR_G         255
#define STATE_1_COLOR_B         0
#define STATE_1_BRIGHTNESS      180

// ============================================================================
// State 2: Stall Danger Zone (Low RPM / Lugging)
// ============================================================================
#define STATE_2_RPM_MIN         0        // Minimum RPM for State 2 (car stalls below 750 anyway)
#define STATE_2_RPM_MAX         1999     // Maximum RPM for State 2

// Animation parameters for outward pulsing effect
#define STATE_2_PULSE_PERIOD    600      // Milliseconds per complete pulse cycle
#define STATE_2_MIN_BRIGHTNESS  20       // Minimum brightness (0-255) during pulse
#define STATE_2_MAX_BRIGHTNESS  200      // Maximum brightness (0-255) during pulse

// Color definition (Orange)
#define STATE_2_COLOR_R         255
#define STATE_2_COLOR_G         80
#define STATE_2_COLOR_B         0

// ============================================================================
// State 3: Normal Driving / Power Band (Mirrored Progress Bar)
// ============================================================================
#define STATE_3_RPM_MIN         2501     // Minimum RPM for State 3
#define STATE_3_RPM_MAX         4500     // Maximum RPM for State 3

// Color definition (Yellow)
#define STATE_3_COLOR_R         255
#define STATE_3_COLOR_G         255
#define STATE_3_COLOR_B         0
#define STATE_3_BRIGHTNESS      255

// ============================================================================
// State 4: High RPM / Shift Danger (Flashing Gap)
// ============================================================================
#define STATE_4_RPM_MIN         4501     // Minimum RPM for State 4
#define STATE_4_RPM_MAX         7199     // Maximum RPM for State 4

// Animation parameters for flashing gap
#define STATE_4_FLASH_SPEED_MIN 150      // Milliseconds between flashes (at threshold)
#define STATE_4_FLASH_SPEED_MAX 40       // Milliseconds between flashes (near redline)

// Color definitions
#define STATE_4_BAR_R           255      // Filled bar color (Red)
#define STATE_4_BAR_G           0
#define STATE_4_BAR_B           0

#define STATE_4_FLASH_1_R       255      // Flash color 1 (Red)
#define STATE_4_FLASH_1_G       0
#define STATE_4_FLASH_1_B       0

#define STATE_4_FLASH_2_R       255      // Flash color 2 (White/Cyan)
#define STATE_4_FLASH_2_G       255
#define STATE_4_FLASH_2_B       255

#define STATE_4_BRIGHTNESS      255

// ============================================================================
// State 5: Rev Limit Cut (Full Strip Red)
// ============================================================================
#define STATE_5_RPM_MIN         7200     // Minimum RPM for State 5 (redline)

// Color definition (Solid Red)
#define STATE_5_COLOR_R         255
#define STATE_5_COLOR_G         0
#define STATE_5_COLOR_B         0
#define STATE_5_BRIGHTNESS      255

// ============================================================================
// Error State: CAN Bus Read Error
// ============================================================================
// Animation parameters for inward pepper effect
#define ERROR_PEPPER_DELAY      80       // Milliseconds between each LED lighting
#define ERROR_HOLD_TIME         300      // Milliseconds to hold full pattern before repeating

// Color definition (Red)
#define ERROR_COLOR_R           255
#define ERROR_COLOR_G           0
#define ERROR_COLOR_B           0
#define ERROR_BRIGHTNESS        200

// ============================================================================
// Helper Macros for State Detection
// ============================================================================
#define IS_STATE_0(speed) ((speed) <= STATE_0_SPEED_THRESHOLD)
#define IS_STATE_1(rpm) ((rpm) >= STATE_1_RPM_MIN && (rpm) <= STATE_1_RPM_MAX)
#define IS_STATE_2(rpm) ((rpm) >= STATE_2_RPM_MIN && (rpm) <= STATE_2_RPM_MAX)
#define IS_STATE_3(rpm) ((rpm) >= STATE_3_RPM_MIN && (rpm) <= STATE_3_RPM_MAX)
#define IS_STATE_4(rpm) ((rpm) >= STATE_4_RPM_MIN && (rpm) <= STATE_4_RPM_MAX)
#define IS_STATE_5(rpm) ((rpm) >= STATE_5_RPM_MIN)

#endif // LED_STATES_H
