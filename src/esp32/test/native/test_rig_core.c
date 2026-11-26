/*
 * Native host test of rig_core (WP09a). Build and run from the repository root:
 *
 *   gcc -std=c99 -Wall -Wextra -Werror -I src/esp32/lib/rig_core \
 *       src/esp32/test/native/test_rig_core.c src/esp32/lib/rig_core/rig_core.c \
 *       -o /tmp/test_rig_core && /tmp/test_rig_core
 *
 * src/shared/tests/test_rig_core_native.py does the same inside unittest.
 * Expected values are written by hand from the D38/D45 rules, not taken from
 * running the code. Times use a 10 s test limit and a 48.5 s test ceiling;
 * these are test numbers only, never firmware values (D34).
 */
#include <stdio.h>
#include <stdlib.h>
#include "rig_core.h"

static int failures = 0;
static int checks = 0;

#define CHECK(cond) do { checks++; if (!(cond)) { failures++; \
    printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); } } while (0)

#define CEILING 48500u
#define LIMIT 10000

static void fresh(rc_state *s)
{
    rc_init(s, CEILING);
}

static void test_no_on_before_limit(void)
{
    rc_state s;
    fresh(&s);
    CHECK(rc_set_pumps(&s, 1, 0, 0) == RC_ERR_NO_LIMIT);
    CHECK(!s.ch[0].commanded && !s.ch[0].effective);
    CHECK(rc_set_pumps(&s, 0, 1, 0) == RC_ERR_NO_LIMIT);
    CHECK(!s.ch[1].effective);
    CHECK(rc_set_pumps(&s, 0, 0, 0) == RC_OK);          /* OFF is always accepted */
}

static void test_limit_rules(void)
{
    rc_state s;
    fresh(&s);
    CHECK(rc_set_limit(&s, 0) == RC_ERR_LIMIT_NOT_POSITIVE);
    CHECK(rc_set_limit(&s, -5) == RC_ERR_LIMIT_NOT_POSITIVE);
    CHECK(rc_set_limit(&s, (int32_t)CEILING + 1) == RC_ERR_LIMIT_ABOVE_CEILING);
    CHECK(s.limit_ms == 0);
    CHECK(rc_set_limit(&s, (int32_t)CEILING) == RC_OK);  /* equal to ceiling allowed */
    CHECK(s.limit_ms == CEILING);
    CHECK(rc_set_limit(&s, LIMIT) == RC_OK);
    CHECK(rc_set_pumps(&s, 1, 0, 100) == RC_OK);
    CHECK(rc_set_limit(&s, 20000) == RC_ERR_PUMPS_ON);   /* no change while ON */
    CHECK(s.limit_ms == LIMIT);
    CHECK(rc_set_pumps(&s, 0, 0, 200) == RC_OK);
    CHECK(rc_set_limit(&s, 20000) == RC_OK);
    CHECK(s.limit_ms == 20000);
}

static void test_bad_arguments_change_nothing(void)
{
    rc_state s;
    fresh(&s);
    rc_set_limit(&s, LIMIT);
    CHECK(rc_set_pumps(&s, 2, 0, 0) == RC_ERR_BAD_ARGUMENT);
    CHECK(rc_set_pumps(&s, 1, -1, 0) == RC_ERR_BAD_ARGUMENT);
    CHECK(!s.ch[0].commanded && !s.ch[1].commanded);
}

static void test_cutoff_fires_at_limit(void)
{
    rc_state s;
    fresh(&s);
    rc_set_limit(&s, LIMIT);
    CHECK(rc_set_pumps(&s, 1, 0, 1000) == RC_OK);        /* ON edge at 1.000 s */
    CHECK(s.ch[0].effective);
    CHECK(rc_poll(&s, 10999) == 0);                     /* 9.999 s ON: still ON */
    CHECK(s.ch[0].effective);
    CHECK(rc_poll(&s, 11000) == 1u);                    /* 10.000 s: trips, reported once */
    CHECK(!s.ch[0].effective && s.ch[0].tripped && s.ch[0].commanded);
    CHECK(rc_poll(&s, 11001) == 0);                     /* not reported again */
    CHECK(rc_poll(&s, 60000) == 0);
    CHECK(!s.ch[0].effective);
}

static void test_repeated_on_does_not_restart_timer(void)
{
    rc_state s;
    fresh(&s);
    rc_set_limit(&s, LIMIT);
    rc_set_pumps(&s, 1, 0, 0);
    rc_set_pumps(&s, 1, 0, 5000);                       /* repeat, no edge */
    CHECK(rc_poll(&s, 10000) == 1u);                    /* still trips at 10 s from 0 */
    rc_set_pumps(&s, 1, 0, 12000);                      /* repeat after trip: stays OFF */
    CHECK(!s.ch[0].effective && s.ch[0].tripped);
    CHECK(rc_poll(&s, 30000) == 0);
}

static void test_new_edge_starts_new_timer(void)
{
    rc_state s;
    fresh(&s);
    rc_set_limit(&s, LIMIT);
    rc_set_pumps(&s, 1, 0, 0);
    CHECK(rc_poll(&s, 10000) == 1u);
    rc_set_pumps(&s, 0, 0, 15000);                      /* OFF clears the trip */
    CHECK(!s.ch[0].tripped && !s.ch[0].commanded);
    rc_set_pumps(&s, 1, 0, 20000);                      /* new edge */
    CHECK(s.ch[0].effective);
    CHECK(rc_poll(&s, 29999) == 0);
    CHECK(rc_poll(&s, 30000) == 1u);
}

static void test_off_before_limit_no_trip(void)
{
    rc_state s;
    fresh(&s);
    rc_set_limit(&s, LIMIT);
    rc_set_pumps(&s, 1, 0, 0);
    rc_poll(&s, 5000);
    rc_set_pumps(&s, 0, 0, 5000);
    CHECK(rc_poll(&s, 10000) == 0);
    CHECK(!s.ch[0].effective && !s.ch[0].tripped);
}

static void test_channels_independent(void)
{
    rc_state s;
    fresh(&s);
    rc_set_limit(&s, LIMIT);
    rc_set_pumps(&s, 1, 0, 0);
    rc_set_pumps(&s, 1, 1, 4000);                       /* ch2 edge at 4 s, ch1 unchanged */
    CHECK(rc_poll(&s, 10000) == 1u);                    /* only ch1 */
    CHECK(s.ch[1].effective);
    CHECK(rc_poll(&s, 13999) == 0);
    CHECK(rc_poll(&s, 14000) == 2u);                    /* ch2 at 4 + 10 s */
    rc_set_limit(&s, LIMIT);                            /* refused: still commanded ON */
    CHECK(rc_set_limit(&s, LIMIT) == RC_ERR_PUMPS_ON);
}

static void test_both_trip_together(void)
{
    rc_state s;
    fresh(&s);
    rc_set_limit(&s, LIMIT);
    rc_set_pumps(&s, 1, 1, 0);
    CHECK(rc_poll(&s, 10000) == 3u);
}

static void test_stop(void)
{
    rc_state s;
    fresh(&s);
    rc_set_limit(&s, LIMIT);
    rc_set_pumps(&s, 1, 1, 0);
    rc_poll(&s, 10000);
    rc_stop(&s);
    CHECK(!s.ch[0].commanded && !s.ch[0].effective && !s.ch[0].tripped);
    CHECK(!s.ch[1].commanded && !s.ch[1].effective && !s.ch[1].tripped);
    CHECK(s.limit_ms == LIMIT);                         /* limit kept */
    CHECK(rc_set_limit(&s, 2000) == RC_OK);             /* allowed after stop */
}

static void test_millis_wraparound(void)
{
    rc_state s;
    uint32_t start = 0xFFFFFFFFu - 3000u;               /* 3 s before millis() wraps */
    fresh(&s);
    rc_set_limit(&s, LIMIT);
    rc_set_pumps(&s, 1, 0, start);
    CHECK(rc_poll(&s, start + 9999u) == 0);             /* wraps past zero */
    CHECK(rc_poll(&s, start + 10000u) == 1u);
}

static void test_on_time(void)
{
    rc_state s;
    fresh(&s);
    rc_set_limit(&s, LIMIT);
    CHECK(rc_on_time_ms(&s, 0, 500) == 0);
    rc_set_pumps(&s, 1, 0, 1000);
    CHECK(rc_on_time_ms(&s, 0, 3500) == 2500);
    CHECK(rc_on_time_ms(&s, 5, 3500) == 0);
}

int main(void)
{
    test_no_on_before_limit();
    test_limit_rules();
    test_bad_arguments_change_nothing();
    test_cutoff_fires_at_limit();
    test_repeated_on_does_not_restart_timer();
    test_new_edge_starts_new_timer();
    test_off_before_limit_no_trip();
    test_channels_independent();
    test_both_trip_together();
    test_stop();
    test_millis_wraparound();
    test_on_time();
    printf("%d checks, %d failures\n", checks, failures);
    return failures == 0 ? EXIT_SUCCESS : EXIT_FAILURE;
}
