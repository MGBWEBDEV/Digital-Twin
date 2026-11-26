/* rig_core: see rig_core.h for the rules implemented here. */
#include "rig_core.h"

void rc_init(rc_state *s, uint32_t ceiling_ms)
{
    int i;
    s->ceiling_ms = ceiling_ms;
    s->limit_ms = 0;
    for (i = 0; i < RC_CHANNELS; i++) {
        s->ch[i].commanded = false;
        s->ch[i].effective = false;
        s->ch[i].tripped = false;
        s->ch[i].on_since_ms = 0;
    }
}

rc_result rc_set_limit(rc_state *s, int32_t limit_ms)
{
    int i;
    for (i = 0; i < RC_CHANNELS; i++) {
        if (s->ch[i].commanded) {
            return RC_ERR_PUMPS_ON;
        }
    }
    if (limit_ms <= 0) {
        return RC_ERR_LIMIT_NOT_POSITIVE;
    }
    if ((uint32_t)limit_ms > s->ceiling_ms) {
        return RC_ERR_LIMIT_ABOVE_CEILING;
    }
    s->limit_ms = (uint32_t)limit_ms;
    return RC_OK;
}

static void command_channel(rc_channel *c, bool on, uint32_t now_ms)
{
    if (!on) {
        c->commanded = false;
        c->effective = false;
        c->tripped = false;
        return;
    }
    if (c->commanded) {
        return;                      /* no OFF -> ON edge: timer and trip unchanged */
    }
    c->commanded = true;
    c->effective = true;
    c->tripped = false;
    c->on_since_ms = now_ms;
}

rc_result rc_set_pumps(rc_state *s, int32_t on_ch1, int32_t on_ch2, uint32_t now_ms)
{
    if ((on_ch1 != 0 && on_ch1 != 1) || (on_ch2 != 0 && on_ch2 != 1)) {
        return RC_ERR_BAD_ARGUMENT;
    }
    if ((on_ch1 || on_ch2) && s->limit_ms == 0) {
        return RC_ERR_NO_LIMIT;
    }
    command_channel(&s->ch[0], on_ch1 == 1, now_ms);
    command_channel(&s->ch[1], on_ch2 == 1, now_ms);
    return RC_OK;
}

void rc_stop(rc_state *s)
{
    int i;
    for (i = 0; i < RC_CHANNELS; i++) {
        command_channel(&s->ch[i], false, 0);
    }
}

unsigned rc_poll(rc_state *s, uint32_t now_ms)
{
    unsigned tripped = 0;
    int i;
    for (i = 0; i < RC_CHANNELS; i++) {
        rc_channel *c = &s->ch[i];
        if (c->effective && (uint32_t)(now_ms - c->on_since_ms) >= s->limit_ms) {
            c->effective = false;
            c->tripped = true;
            tripped |= 1u << i;
        }
    }
    return tripped;
}

uint32_t rc_on_time_ms(const rc_state *s, int channel, uint32_t now_ms)
{
    const rc_channel *c;
    if (channel < 0 || channel >= RC_CHANNELS) {
        return 0;
    }
    c = &s->ch[channel];
    return c->commanded ? (uint32_t)(now_ms - c->on_since_ms) : 0;
}

const char *rc_result_name(rc_result r)
{
    switch (r) {
    case RC_OK: return "ok";
    case RC_ERR_LIMIT_NOT_POSITIVE: return "limit_not_positive";
    case RC_ERR_LIMIT_ABOVE_CEILING: return "limit_above_ceiling";
    case RC_ERR_PUMPS_ON: return "pumps_on";
    case RC_ERR_NO_LIMIT: return "no_limit";
    case RC_ERR_BAD_ARGUMENT: return "bad_argument";
    }
    return "unknown";
}
