/*
 * rig_core: pump switching and safety cut-off of the rig I/O firmware (WP09a).
 *
 * Plain C (C99) with no Arduino dependency, so the same file is compiled into
 * the ESP32 firmware and into the native host test (test/native). It holds
 * only state and rules; the caller reads millis() and writes the outputs.
 *
 * Cut-off semantics (D27, D38, D45; design/software_architecture.md section 6),
 * identical to src/shared/cutoff.py:
 *   - a timer per pump counts continuous ON time from the moment the ON
 *     command (an OFF -> ON edge of the commanded state) is received;
 *   - when it reaches the per-run limit the pump is forced OFF and the trip
 *     is reported once;
 *   - the pump stays OFF while the commanded state stays ON; only a new
 *     OFF -> ON edge starts a new timer;
 *   - a repeated ON command without an OFF in between changes nothing.
 *
 * Limit rules (D45, D49):
 *   - no pump can be switched ON until a limit has been set (limit 0 = unset);
 *   - a limit must satisfy 0 < limit <= ceiling (compiled in);
 *   - a limit can only be changed while both pumps are commanded OFF.
 */
#ifndef RIG_CORE_H
#define RIG_CORE_H

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define RC_CHANNELS 2

/* Result codes. Text names are in rc_result_name(). */
typedef enum {
    RC_OK = 0,
    RC_ERR_LIMIT_NOT_POSITIVE,   /* set_limit with 0 or a negative value */
    RC_ERR_LIMIT_ABOVE_CEILING,  /* set_limit above the compiled-in ceiling */
    RC_ERR_PUMPS_ON,             /* set_limit while a pump is commanded ON */
    RC_ERR_NO_LIMIT,             /* ON requested before any limit was set */
    RC_ERR_BAD_ARGUMENT          /* argument outside its allowed values */
} rc_result;

typedef struct {
    bool commanded;        /* last state commanded by the host */
    bool effective;        /* state applied to the pump output */
    bool tripped;          /* cut-off fired; latched until commanded OFF */
    uint32_t on_since_ms;  /* time of the OFF -> ON edge (valid while commanded) */
} rc_channel;

typedef struct {
    uint32_t ceiling_ms;   /* compiled-in maximum for any limit */
    uint32_t limit_ms;     /* per-run limit; 0 = not set */
    rc_channel ch[RC_CHANNELS];
} rc_state;

/* All pumps OFF, no limit set. ceiling_ms must be > 0. */
void rc_init(rc_state *s, uint32_t ceiling_ms);

/* Set the per-run limit. limit_ms is signed so that a negative value sent by
 * the host is rejected rather than wrapped. */
rc_result rc_set_limit(rc_state *s, int32_t limit_ms);

/* Command both channels at once (index 0 = driver channel 1, index 1 =
 * driver channel 2). Each value must be 0 or 1. On any error nothing changes. */
rc_result rc_set_pumps(rc_state *s, int32_t on_ch1, int32_t on_ch2, uint32_t now_ms);

/* Command both pumps OFF and clear the trips. The limit is kept. */
void rc_stop(rc_state *s);

/* Apply the cut-off at now_ms. Returns a bit mask of channels that tripped
 * in this call (bit 0 = channel 1, bit 1 = channel 2). Call as often as
 * possible; times are compared with unsigned wrap-around arithmetic. */
unsigned rc_poll(rc_state *s, uint32_t now_ms);

/* Continuous ON time of a commanded channel at now_ms (0 if commanded OFF). */
uint32_t rc_on_time_ms(const rc_state *s, int channel, uint32_t now_ms);

const char *rc_result_name(rc_result r);

#ifdef __cplusplus
}
#endif

#endif /* RIG_CORE_H */
