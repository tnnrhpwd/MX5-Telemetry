#ifndef LED_STATES_H
#define LED_STATES_H

// ============================================================================
// LED Strip State Definitions - Mirrored Progress Bar System
// ============================================================================
// This file defines the LED strip states with a mirrored progress bar.
// These constants are shared between the master and slave Arduino.
// ============================================================================
// 
// 🎨 STATE 0: IDLE/NEUTRAL (Speed = 0, not moving)
// -------------------------------------------------
// Visual: White LEDs sequentially pepper inward from edges to center
// Purpose: Indicates vehicle is stationary (neutral/clutch engaged)
// Pattern: ⚪ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ → ⚪ ⚪ ⚫ ⚫ ⚫ ⚫ ⚪ ⚪
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
// State 0: Idle/Neutral (Vehicle Not Moving)
// ============================================================================
#define STATE_0_SPEED_THRESHOLD 1        // Speed <= 1 km/h triggers this state
#define STATE_0_RPM_MAX         800      // Max RPM for idle state (normal idle ~750-800)

// Animation parameters for inward pepper effect
#define STATE_0_PEPPER_DELAY    80       // Milliseconds between each LED lighting
#define STATE_0_HOLD_TIME       300      // Milliseconds to hold full pattern before repeating

// Color definition (White)
#define STATE_0_COLOR_R         255
#define STATE_0_COLOR_G         255
#define STATE_0_COLOR_B         255

// ============================================================================
// Normal Driving Zone: Blue-Green-Yellow Gradient Bar (2000-4500 RPM)
// ============================================================================
// Smooth color gradient based on efficiency zones:
//   BLUE   (2000-2500 RPM): Best Absolute Gas Efficiency (MPG)
//   GREEN  (2500-4000 RPM): Best Thermal Efficiency (Power-to-Gas)
//   YELLOW (4000-4500 RPM): Approaching High RPM
// ============================================================================
#define NORMAL_RPM_MIN          2000     // Start of normal driving zone
#define NORMAL_RPM_MAX          4500     // End of normal driving zone

// Efficiency zone RPM thresholds (for color interpolation)
#define EFFICIENCY_BLUE_END     2500     // End of best MPG zone (blue)
#define EFFICIENCY_GREEN_END    4000     // End of thermal efficiency zone (green)
// Yellow continues from 4000 to NORMAL_RPM_MAX (4500)

// Color definitions for efficiency zones
#define BLUE_COLOR_R            0
#define BLUE_COLOR_G            100      // Slight green tint for visibility
#define BLUE_COLOR_B            255

#define GREEN_COLOR_R           0
#define GREEN_COLOR_G           255
#define GREEN_COLOR_B           0

#define YELLOW_COLOR_R          255
#define YELLOW_COLOR_G          255
#define YELLOW_COLOR_B          0

// Legacy defines kept for compatibility
#define STATE_1_RPM_MIN         2000
#define STATE_1_RPM_MAX         2500
#define STATE_1_LEDS_PER_SIDE   2
#define STATE_1_COLOR_R         0
#define STATE_1_COLOR_G         255
#define STATE_1_COLOR_B         0
#define STATE_3_RPM_MIN         2501
#define STATE_3_RPM_MAX         4500
#define STATE_3_COLOR_R         255
#define STATE_3_COLOR_G         255
#define STATE_3_COLOR_B         0
#define STATE_2_MIN_BRIGHTNESS  20       // Minimum brightness (0-255) during pulse
#define STATE_2_MAX_BRIGHTNESS  200      // Maximum brightness (0-255) during pulse

// Color definition (Orange)
#define STATE_2_COLOR_R         255
#define STATE_2_COLOR_G         80
#define STATE_3_COLOR_B         0

// ============================================================================
// State 2: Stall Danger Zone (Low RPM / Lugging)
// ============================================================================
#define STATE_2_RPM_MIN         0        // Minimum RPM for State 2 (car stalls below 750 anyway)
#define STATE_2_RPM_MAX         1999     // Maximum RPM for State 2

// Color definition (Orange)
#define STATE_2_COLOR_R         255
#define STATE_2_COLOR_G         80
#define STATE_2_COLOR_B         0

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

#define STATE_4_FLASH_2_R       255      // Flash color 2 (White)
#define STATE_4_FLASH_2_G       255
#define STATE_4_FLASH_2_B       255

// ============================================================================
// State 5: Rev Limit Cut (Full Strip Red)
// ============================================================================
#define STATE_5_RPM_MIN         7200     // Minimum RPM for State 5 (redline)

// Color definition (Solid Red)
#define STATE_5_COLOR_R         255
#define STATE_5_COLOR_G         0
#define STATE_5_COLOR_B         0

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

#endif // LED_STATES_H
