/*
 * Rig I/O firmware (WP09a), derived from LabAutomationKits StepExample
 * (references/LabAutomationKits/Electronics/Firmware/StepExample, upstream
 * commit a22a6b9; D32).
 *
 * Kept from StepExample: board and toolchain (platformio.ini), CmdMessenger
 * on Serial at 115200 baud with ',' ';' '/' separators, the watchdog
 * identifier reply, and the driver pins and PWM calls of DF4MotorDriver.
 * Changed (WP09a, D21, D27, D38, D45):
 *   - both driver channels are switched, independently, by one command;
 *   - the timed kStep is replaced by a per-run "set limit" command and a
 *     maximum-continuous-ON-time cut-off (rig_core), bounded by the
 *     compiled-in ceiling; the cut-off is reported with kCutoff;
 *   - speed and direction are fixed in rig_config.h (D20), not sent per command;
 *   - the level sensor is reported on change and on request (raw level);
 *   - a start-up message (kStarted) lets the host detect a restart (WP06 X8);
 *   - arguments are sent as text so that the host needs only pyserial.
 * The firmware contains no controller logic (D30): it switches the pumps
 * only as commanded and only within the cut-off.
 *
 * Message table: src/esp32/README.md. The same IDs are in
 * src/shared/rig_protocol.py.
 */
#include <Arduino.h>
#include <CmdMessenger.h>
#include "rig_config.h"
#include "rig_core.h"

#define FIRMWARE_NAME "dt-rig-io"
#define FIRMWARE_VERSION "0.1.0"
// Watchdog identifier kept from StepExample.
#define DEVICE_ID "0000000-0000-0000-0000-00000000001"

CmdMessenger cmdMessenger(Serial, ',', ';', '/');

// Message IDs. Keep in the same order as src/shared/rig_protocol.py.
enum
{
  kWatchdog,   // host -> fw: request identifier; fw -> host: identifier
  kStarted,    // fw -> host: firmware has (re)started
  kError,      // fw -> host: code [, detail]
  kGetInfo,    // host -> fw
  kInfo,       // fw -> host: firmware and configuration values
  kSetLimit,   // host -> fw: limit_ms
  kLimitSet,   // fw -> host: limit_ms
  kSetPumps,   // host -> fw: on_ch1 (0/1), on_ch2 (0/1)
  kPumps,      // fw -> host: cmd1, eff1, cmd2, eff2, fw_ms (reply to kSetPumps/kStop)
  kStop,       // host -> fw: both pumps OFF
  kGetState,   // host -> fw
  kState,      // fw -> host: cmd1, eff1, trip1, cmd2, eff2, trip2, limit_ms, sensor, fw_ms
  kGetSensor,  // host -> fw
  kSensor,     // fw -> host: raw level (0/1, -1 = not wired), fw_ms
  kCutoff,     // fw -> host: channel (1/2), on_ms, fw_ms
};

static const uint8_t PWM_PIN[RC_CHANNELS] = {CH1_PWM_PIN, CH2_PWM_PIN};
static const uint8_t DIR_PIN[RC_CHANNELS] = {CH1_DIR_PIN, CH2_DIR_PIN};
static const uint16_t SPEED[RC_CHANNELS] = {CH1_SPEED, CH2_SPEED};
static const uint8_t DIR_LEVEL[RC_CHANNELS] = {CH1_DIR_LEVEL, CH2_DIR_LEVEL};

static rc_state core;
static bool applied[RC_CHANNELS] = {false, false};
static int lastSensor = -2;   // forces a first report

// ------------------  O U T P U T S  ------------------

static void allDriverOutputsOff()
{
  const uint8_t pwm[] = {CH1_PWM_PIN, CH2_PWM_PIN, CH3_PWM_PIN, CH4_PWM_PIN};
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
  // Core 3.x: per-pin call; on a pin not yet attached it sets the resolution
  // used when analogWrite() first attaches the pin (esp32-hal-ledc.c).
  for (uint8_t i = 0; i < sizeof(pwm); i++)
  {
    analogWriteResolution(pwm[i], PWM_RESOLUTION_BITS);
  }
#else
  // Core 2.x: global call, as in StepExample.
  analogWriteResolution(PWM_RESOLUTION_BITS);
#endif
  for (uint8_t i = 0; i < sizeof(pwm); i++)
  {
    pinMode(pwm[i], OUTPUT);
    analogWrite(pwm[i], 0);
  }
  for (uint8_t i = 0; i < RC_CHANNELS; i++)
  {
    pinMode(DIR_PIN[i], OUTPUT);
    digitalWrite(DIR_PIN[i], DIR_LEVEL[i]);
    applied[i] = false;
  }
}

// Bring the driver outputs in line with rig_core's effective states.
static void writeOutputs()
{
  for (uint8_t i = 0; i < RC_CHANNELS; i++)
  {
    bool on = core.ch[i].effective;
    if (on == applied[i])
    {
      continue;
    }
    if (on)
    {
      digitalWrite(DIR_PIN[i], DIR_LEVEL[i]);
      analogWrite(PWM_PIN[i], SPEED[i]);
    }
    else
    {
      analogWrite(PWM_PIN[i], 0);
    }
    applied[i] = on;
  }
}

// Apply the cut-off: outputs first, report afterwards (sending may take time).
static void pollCutoff()
{
  unsigned tripped = rc_poll(&core, millis());
  if (!tripped)
  {
    return;
  }
  writeOutputs();
  uint32_t now = millis();
  for (uint8_t i = 0; i < RC_CHANNELS; i++)
  {
    if (tripped & (1u << i))
    {
      cmdMessenger.sendCmdStart(kCutoff);
      cmdMessenger.sendCmdArg(i + 1);
      cmdMessenger.sendCmdArg(core.limit_ms);
      cmdMessenger.sendCmdArg(now);
      cmdMessenger.sendCmdEnd();
    }
  }
}

// ------------------  S E N S O R  ------------------

static int readSensor()
{
#if SENSOR_PIN >= 0
  return digitalRead(SENSOR_PIN) == HIGH ? 1 : 0;
#else
  return -1;
#endif
}

static void sendSensor(int level)
{
  cmdMessenger.sendCmdStart(kSensor);
  cmdMessenger.sendCmdArg(level);
  cmdMessenger.sendCmdArg((uint32_t)millis());
  cmdMessenger.sendCmdEnd();
}

static void pollSensor()
{
  int level = readSensor();
  if (level != lastSensor)
  {
    lastSensor = level;
    sendSensor(level);
  }
}

// ------------------  R E P L I E S  ------------------

static void sendError(const char *code)
{
  cmdMessenger.sendCmd(kError, code);
}

static void sendPumps()
{
  cmdMessenger.sendCmdStart(kPumps);
  cmdMessenger.sendCmdArg(core.ch[0].commanded ? 1 : 0);
  cmdMessenger.sendCmdArg(core.ch[0].effective ? 1 : 0);
  cmdMessenger.sendCmdArg(core.ch[1].commanded ? 1 : 0);
  cmdMessenger.sendCmdArg(core.ch[1].effective ? 1 : 0);
  cmdMessenger.sendCmdArg((uint32_t)millis());
  cmdMessenger.sendCmdEnd();
}

// ------------------  C A L L B A C K S  ------------------

void OnUnknownCommand()
{
  sendError("unknown_command");
}

void OnWatchdog()
{
  cmdMessenger.sendCmd(kWatchdog, DEVICE_ID);
}

void OnGetInfo()
{
  cmdMessenger.sendCmdStart(kInfo);
  cmdMessenger.sendCmdArg(FIRMWARE_NAME);
  cmdMessenger.sendCmdArg(FIRMWARE_VERSION);
  cmdMessenger.sendCmdArg((uint32_t)CUTOFF_CEILING_MS);
  cmdMessenger.sendCmdArg(CH1_PWM_PIN);
  cmdMessenger.sendCmdArg(CH1_DIR_PIN);
  cmdMessenger.sendCmdArg(CH1_SPEED);
  cmdMessenger.sendCmdArg(CH1_DIR_LEVEL);
  cmdMessenger.sendCmdArg(CH2_PWM_PIN);
  cmdMessenger.sendCmdArg(CH2_DIR_PIN);
  cmdMessenger.sendCmdArg(CH2_SPEED);
  cmdMessenger.sendCmdArg(CH2_DIR_LEVEL);
  cmdMessenger.sendCmdArg(SENSOR_PIN);
  cmdMessenger.sendCmdEnd();
}

void OnSetLimit()
{
  int32_t limit = cmdMessenger.readInt32Arg();
  if (!cmdMessenger.isArgOk())
  {
    sendError("bad_argument");
    return;
  }
  rc_result r = rc_set_limit(&core, limit);
  if (r != RC_OK)
  {
    sendError(rc_result_name(r));
    return;
  }
  cmdMessenger.sendCmdStart(kLimitSet);
  cmdMessenger.sendCmdArg(core.limit_ms);
  cmdMessenger.sendCmdEnd();
}

void OnSetPumps()
{
  int32_t on1 = cmdMessenger.readInt32Arg();
  bool ok1 = cmdMessenger.isArgOk();
  int32_t on2 = cmdMessenger.readInt32Arg();
  bool ok2 = cmdMessenger.isArgOk();
  if (!ok1 || !ok2)
  {
    sendError("bad_argument");
    return;
  }
  pollCutoff();   // a trip that is already due is applied before the new command
  rc_result r = rc_set_pumps(&core, on1, on2, millis());
  writeOutputs();
  if (r != RC_OK)
  {
    sendError(rc_result_name(r));
    return;
  }
  sendPumps();
}

void OnStop()
{
  rc_stop(&core);
  writeOutputs();
  sendPumps();
}

void OnGetState()
{
  cmdMessenger.sendCmdStart(kState);
  for (uint8_t i = 0; i < RC_CHANNELS; i++)
  {
    cmdMessenger.sendCmdArg(core.ch[i].commanded ? 1 : 0);
    cmdMessenger.sendCmdArg(core.ch[i].effective ? 1 : 0);
    cmdMessenger.sendCmdArg(core.ch[i].tripped ? 1 : 0);
  }
  cmdMessenger.sendCmdArg(core.limit_ms);
  cmdMessenger.sendCmdArg(readSensor());
  cmdMessenger.sendCmdArg((uint32_t)millis());
  cmdMessenger.sendCmdEnd();
}

void OnGetSensor()
{
  sendSensor(readSensor());
}

static void attachCommandCallbacks()
{
  cmdMessenger.attach(OnUnknownCommand);
  cmdMessenger.attach(kWatchdog, OnWatchdog);
  cmdMessenger.attach(kGetInfo, OnGetInfo);
  cmdMessenger.attach(kSetLimit, OnSetLimit);
  cmdMessenger.attach(kSetPumps, OnSetPumps);
  cmdMessenger.attach(kStop, OnStop);
  cmdMessenger.attach(kGetState, OnGetState);
  cmdMessenger.attach(kGetSensor, OnGetSensor);
}

// ------------------  S E T U P  /  L O O P  ------------------

void setup()
{
  // Pumps OFF before anything else (StepExample only set the pin modes).
  allDriverOutputsOff();
  rc_init(&core, CUTOFF_CEILING_MS);
#if SENSOR_PIN >= 0
  pinMode(SENSOR_PIN, SENSOR_PIN_MODE);
#endif

  Serial.begin(115200);
  cmdMessenger.printLfCr(true);   // one message per line; the host ignores the line ends
  attachCommandCallbacks();

  cmdMessenger.sendCmdStart(kStarted);
  cmdMessenger.sendCmdArg(FIRMWARE_NAME);
  cmdMessenger.sendCmdArg(FIRMWARE_VERSION);
  cmdMessenger.sendCmdEnd();
}

void loop()
{
  pollCutoff();
  cmdMessenger.feedinSerialData();
  pollCutoff();
  pollSensor();
}
