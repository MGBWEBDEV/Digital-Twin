/*
 * rig_config.h: every rig-specific value of the WP09a firmware, in one place.
 *
 * NONE OF THESE VALUES IS CONFIRMED. The pins come from the unchanged
 * StepExample code (D32, "derived from code"); speed and direction are the
 * placeholder P19; the cut-off ceiling has no value at all. Before any build
 * that is uploaded to the board (researcher approval required):
 *   1. Check pins, channel assignment, speed and direction against the rig
 *      (design/physical_system.md section 10; U20, U22, U24; P17, P19).
 *   2. Set CUTOFF_CEILING_MS to the largest T_max of the approved session
 *      plan (D45; experiments/experimental_protocol.md section 8). It is a
 *      safety limit, so it is never a placeholder (D34).
 *   3. Set SENSOR_PIN once the sensor is wired (D19), else leave -1.
 *   4. Set RIG_CONFIG_REVIEWED to 1 and record the change and the firmware
 *      hash in the session log (protocol section 16).
 * The firmware reports all of these values in its kInfo reply, and the host
 * adapter logs them in run.json.
 */
#ifndef RIG_CONFIG_H
#define RIG_CONFIG_H

/* Set to 1 only after the review above. The build fails while it is 0. */
#define RIG_CONFIG_REVIEWED 0

/* Cut-off ceiling in ms (D45): largest T_max of the session plan. 0 = not set;
 * the build fails while it is 0. Example only, not a value: a plan whose
 * largest T_max is 48.5 s gives 48500. */
#define CUTOFF_CEILING_MS 0

/* Driver channel 1 (StepExample pump A): placeholder P17 says intake. */
#define CH1_PWM_PIN 8
#define CH1_DIR_PIN 9
#define CH1_SPEED 4095      /* P19 placeholder: 12-bit full scale */
#define CH1_DIR_LEVEL 1     /* P19 placeholder: DIR high */

/* Driver channel 2 (StepExample pump B): placeholder P17 says outtake. */
#define CH2_PWM_PIN 16
#define CH2_DIR_PIN 21
#define CH2_SPEED 4095
#define CH2_DIR_LEVEL 1

/* Unused driver channels 3 and 4 (StepExample pins): forced OFF at start-up. */
#define CH3_PWM_PIN 10
#define CH4_PWM_PIN 11

/* PWM resolution used by StepExample (analogWriteResolution(12)). */
#define PWM_RESOLUTION_BITS 12

/* Level sensor (D19: not yet wired). -1 = not wired: the firmware reports
 * the sensor as -1 and the host refuses runs that need it. The firmware
 * reports the raw pin level (0/1); the host normalizes it to wet/dry (P18). */
#define SENSOR_PIN -1
#define SENSOR_PIN_MODE INPUT   /* INPUT, INPUT_PULLUP or INPUT_PULLDOWN (U14) */

/* ---- Build-time checks ------------------------------------------------- */
#if RIG_CONFIG_REVIEWED != 1
#error "rig_config.h not reviewed: check every value against the rig, then set RIG_CONFIG_REVIEWED to 1"
#endif
#if CUTOFF_CEILING_MS <= 0
#error "CUTOFF_CEILING_MS not set: use the largest T_max of the approved session plan (D45)"
#endif
#if (CH1_SPEED < 0) || (CH1_SPEED >= (1 << PWM_RESOLUTION_BITS)) || \
    (CH2_SPEED < 0) || (CH2_SPEED >= (1 << PWM_RESOLUTION_BITS))
#error "pump speed outside the PWM range"
#endif
#if SENSOR_PIN >= 0 && (SENSOR_PIN == CH1_PWM_PIN || SENSOR_PIN == CH1_DIR_PIN || \
    SENSOR_PIN == CH2_PWM_PIN || SENSOR_PIN == CH2_DIR_PIN || \
    SENSOR_PIN == CH3_PWM_PIN || SENSOR_PIN == CH4_PWM_PIN)
#error "SENSOR_PIN collides with a motor driver pin"
#endif

#endif /* RIG_CONFIG_H */
