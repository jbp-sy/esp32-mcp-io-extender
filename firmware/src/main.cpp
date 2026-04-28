#include <Arduino.h>
#include <ArduinoJson.h>

#include <map>
#include <ctype.h>

namespace {

constexpr const char *kProtocolName = "esp32-gpio-jsonl";
constexpr const char *kProtocolVersion = "1.1.0";
constexpr const char *kFirmwareVersion = "0.2.0";
constexpr size_t kMaxLineLength = 512;
constexpr size_t kMaxUartReadBytes = 512;
constexpr size_t kMaxUartWriteBytes = 512;

#if defined(ESP32_MCP_PROFILE_ESP32S3_FH4R2)
constexpr const char *kBoardId = "esp32-s3-fh4r2";
constexpr const char *kBoardProfile = "esp32-s3-fh4r2-safe-v1";
constexpr int kDefaultUartRxPin = 16;
constexpr int kDefaultUartTxPin = 17;
constexpr int kPolicyMaxPin = 48;
#else
constexpr const char *kBoardId = "esp-rs-esp32-c3";
constexpr const char *kBoardProfile = "esp-rs-c3-photo-assumed-v1";
constexpr int kDefaultUartRxPin = 20;
constexpr int kDefaultUartTxPin = 21;
constexpr int kPolicyMaxPin = 21;
#endif

struct UartState {
  bool open;
  uint32_t baud;
  int rxPin;
  int txPin;
  int dataBits;
  char parity;
  int stopBits;
  uint32_t timeoutMs;

  UartState()
      : open(false),
        baud(115200),
        rxPin(kDefaultUartRxPin),
        txPin(kDefaultUartTxPin),
        dataBits(8),
        parity('N'),
        stopBits(1),
        timeoutMs(20) {}
};

struct PwmConfig {
  bool enabled;
  uint32_t freq;
  uint8_t resolution;
  uint32_t value;

  PwmConfig() : enabled(false), freq(5000), resolution(8), value(0) {}
  PwmConfig(bool e, uint32_t f, uint8_t r, uint32_t v) : enabled(e), freq(f), resolution(r), value(v) {}
};

struct PinPolicy {
  bool exists;
  bool blocked;
  bool digitalIn;
  bool digitalOut;
  bool adc;
  bool pwm;
  const char *label;
  const char *reason;

  PinPolicy()
      : exists(false),
        blocked(true),
        digitalIn(false),
        digitalOut(false),
        adc(false),
        pwm(false),
        label("unknown"),
        reason("not_in_profile") {}
  PinPolicy(bool e, bool b, bool din, bool dout, bool a, bool p, const char *l, const char *r)
      : exists(e), blocked(b), digitalIn(din), digitalOut(dout), adc(a), pwm(p), label(l), reason(r) {}
};

std::map<int, String> g_pinModes;
std::map<int, int> g_lastDigital;
std::map<int, PwmConfig> g_pwmStates;
std::map<int, int> g_pwmChannels;
String g_inputBuffer;
bool g_overflow = false;
int g_nextPwmChannel = 0;
constexpr int kMaxPwmChannels = 6;
UartState g_uartState;

bool str_eq(const char *a, const char *b) {
  return strcmp(a, b) == 0;
}

bool cmd_is(const char *cmd, const char *a, const char *b = nullptr) {
  if (str_eq(cmd, a)) {
    return true;
  }
  return b != nullptr && str_eq(cmd, b);
}

PinPolicy policy_for_pin(int pin) {
#if defined(ESP32_MCP_PROFILE_ESP32S3_FH4R2)
  switch (pin) {
    case 0:
      return PinPolicy(true, true, false, false, false, false, "GPIO0", "boot_strap");
    case 1:
      return PinPolicy(true, false, true, true, true, true, "GPIO1/A0", "allowed");
    case 2:
      return PinPolicy(true, false, true, true, true, true, "GPIO2/A1", "allowed");
    case 3:
      return PinPolicy(true, true, false, false, false, false, "GPIO3", "boot_strap");
    case 4:
      return PinPolicy(true, false, true, true, true, true, "GPIO4/A2", "allowed");
    case 5:
      return PinPolicy(true, false, true, true, true, true, "GPIO5/A3", "allowed");
    case 6:
      return PinPolicy(true, false, true, true, true, true, "GPIO6/A4", "allowed");
    case 7:
      return PinPolicy(true, false, true, true, true, true, "GPIO7/A5", "allowed");
    case 8:
      return PinPolicy(true, false, true, true, true, true, "GPIO8/A6", "allowed");
    case 9:
      return PinPolicy(true, false, true, true, true, true, "GPIO9/A7", "allowed");
    case 10:
      return PinPolicy(true, false, true, true, true, true, "GPIO10/A8", "allowed");
    case 11:
      return PinPolicy(true, false, true, true, false, true, "GPIO11", "allowed");
    case 12:
      return PinPolicy(true, false, true, true, false, true, "GPIO12", "allowed");
    case 13:
      return PinPolicy(true, false, true, true, false, true, "GPIO13", "allowed");
    case 14:
      return PinPolicy(true, false, true, true, false, true, "GPIO14", "allowed");
    case 15:
      return PinPolicy(true, false, true, true, false, true, "GPIO15", "allowed");
    case 16:
      return PinPolicy(true, true, false, false, false, false, "GPIO16", "uart_rx_reserved");
    case 17:
      return PinPolicy(true, true, false, false, false, false, "GPIO17", "uart_tx_reserved");
    case 18:
      return PinPolicy(true, false, true, true, false, true, "GPIO18", "allowed");
    case 19:
      return PinPolicy(true, true, false, false, false, false, "GPIO19", "usb_d_minus");
    case 20:
      return PinPolicy(true, true, false, false, false, false, "GPIO20", "usb_d_plus");
    case 21:
      return PinPolicy(true, false, true, true, false, true, "GPIO21", "allowed");
    case 22:
    case 23:
    case 24:
    case 25:
      return PinPolicy(true, true, false, false, false, false, "NC", "not_exposed_on_board");
    case 26:
    case 27:
    case 28:
    case 29:
    case 30:
    case 31:
    case 32:
      return PinPolicy(true, true, false, false, false, false, "GPIO26-32", "spi_flash_psram_internal");
    case 33:
    case 34:
    case 35:
    case 36:
    case 37:
    case 38:
    case 39:
    case 40:
    case 41:
    case 42:
      return PinPolicy(true, true, false, false, false, false, "GPIO33-42", "not_exposed_on_board");
    case 43:
      return PinPolicy(true, true, false, false, false, false, "GPIO43", "uart0_tx_console");
    case 44:
      return PinPolicy(true, true, false, false, false, false, "GPIO44", "uart0_rx_console");
    case 45:
    case 46:
      return PinPolicy(true, true, false, false, false, false, "GPIO45/46", "strap_input_only");
    case 47:
      return PinPolicy(true, true, false, false, false, false, "GPIO47", "reserved_onboard_rgb_led");
    case 48:
      return PinPolicy(true, true, false, false, false, false, "GPIO48", "reserved_onboard_button");
    default:
      return PinPolicy();
  }
#else
  switch (pin) {
    case 0:
      return PinPolicy(true, false, true, true, true, true, "GPIO0/A0", "allowed");
    case 1:
      return PinPolicy(true, false, true, true, true, true, "GPIO1/A1", "allowed");
    case 2:
      return PinPolicy(true, true, false, false, false, false, "GPIO2/A2", "reserved_onboard_rgb_led");
    case 3:
      return PinPolicy(true, false, true, true, true, true, "GPIO3/A3", "allowed");
    case 4:
      return PinPolicy(true, false, true, true, true, true, "GPIO4/A4", "allowed");
    case 5:
      return PinPolicy(true, false, true, true, true, true, "GPIO5/A5", "allowed");
    case 6:
      return PinPolicy(true, true, false, false, false, false, "GPIO6", "reserved_onboard_i2c_scl");
    case 7:
      return PinPolicy(true, false, true, true, false, true, "GPIO7", "allowed");
    case 8:
      return PinPolicy(true, true, false, false, false, false, "GPIO8", "reserved_strap_uncertain");
    case 9:
      return PinPolicy(true, true, false, false, false, false, "GPIO9", "boot_button_strap");
    case 10:
      return PinPolicy(true, true, false, false, false, false, "GPIO10", "reserved_onboard_i2c_sda");
    case 11:
    case 12:
    case 13:
    case 14:
    case 15:
    case 16:
    case 17:
      return PinPolicy(true, true, false, false, false, false, "NC", "not_exposed_on_board");
    case 18:
      return PinPolicy(true, true, false, false, false, false, "GPIO18", "usb_d_plus");
    case 19:
      return PinPolicy(true, true, false, false, false, false, "GPIO19", "usb_d_minus");
    case 20:
      return PinPolicy(true, true, false, false, false, false, "GPIO20", "uart_rx_reserved");
    case 21:
      return PinPolicy(true, true, false, false, false, false, "GPIO21", "uart_tx_reserved");
    default:
      return PinPolicy();
  }
#endif
}

void add_named_pins(JsonObject named) {
#if defined(ESP32_MCP_PROFILE_ESP32S3_FH4R2)
  named["safe_gpio4"] = 4;
  named["safe_gpio5"] = 5;
  named["safe_gpio6"] = 6;
  named["safe_gpio7"] = 7;
  named["adc_a0"] = 1;
  named["adc_a1"] = 2;
#else
  named["safe_gpio3"] = 3;
  named["safe_gpio4"] = 4;
  named["safe_gpio5"] = 5;
  named["safe_gpio7"] = 7;
  named["adc_a0"] = 0;
  named["adc_a1"] = 1;
#endif

  named["uart_rx"] = kDefaultUartRxPin;
  named["uart_tx"] = kDefaultUartTxPin;
}

void add_meta(JsonDocument &res) {
  JsonObject meta = res["meta"].to<JsonObject>();
  meta["protocol"] = kProtocolName;
  meta["protocol_version"] = kProtocolVersion;
  meta["firmware_version"] = kFirmwareVersion;
  meta["board_id"] = kBoardId;
  meta["board_profile"] = kBoardProfile;
  meta["uptime_ms"] = millis();
}

void attach_id(JsonVariantConst req, JsonDocument &res) {
  if (!req.isNull() && req["id"].is<JsonVariantConst>()) {
    res["id"] = req["id"].as<JsonVariantConst>();
  }
}

void reply_ok(JsonVariantConst req, JsonDocument &res) {
  res.clear();
  res["ok"] = true;
  attach_id(req, res);
  add_meta(res);
}

JsonObject reply_error(JsonVariantConst req, JsonDocument &res, const char *code, const char *message) {
  res.clear();
  res["ok"] = false;
  attach_id(req, res);
  JsonObject error = res["error"].to<JsonObject>();
  error["code"] = code;
  error["message"] = message;
  add_meta(res);
  return error["details"].to<JsonObject>();
}

void send_json(const JsonDocument &doc) {
  serializeJson(doc, Serial);
  Serial.println();
}

bool ensure_mode_output(JsonVariantConst req, JsonDocument &res, int pin) {
  auto it = g_pinModes.find(pin);
  if (it == g_pinModes.end()) {
    JsonObject details = reply_error(req, res, "mode_not_set", "set output mode before writing");
    details["pin"] = pin;
    return false;
  }
  if (it->second != "output" && it->second != "output_open_drain") {
    JsonObject details = reply_error(req, res, "mode_not_output", "pin mode is not output");
    details["pin"] = pin;
    details["mode"] = it->second;
    return false;
  }
  return true;
}

bool set_pin_mode_hw(int pin, const String &mode) {
  if (mode == "input") {
    pinMode(pin, INPUT);
  } else if (mode == "input_pullup") {
    pinMode(pin, INPUT_PULLUP);
  } else if (mode == "input_pulldown") {
#ifdef INPUT_PULLDOWN
    pinMode(pin, INPUT_PULLDOWN);
#else
    return false;
#endif
  } else if (mode == "output") {
    pinMode(pin, OUTPUT);
  } else if (mode == "output_open_drain") {
#ifdef OUTPUT_OPEN_DRAIN
    pinMode(pin, OUTPUT_OPEN_DRAIN);
#else
    return false;
#endif
  } else {
    return false;
  }
  g_pinModes[pin] = mode;
  return true;
}

bool check_pin_policy(JsonVariantConst req, JsonDocument &res, int pin, const char *capability) {
  PinPolicy policy = policy_for_pin(pin);
  if (!policy.exists) {
    JsonObject details = reply_error(req, res, "pin_out_of_profile", "pin is not in this board profile");
    details["pin"] = pin;
    return false;
  }

  if (policy.blocked) {
    JsonObject details = reply_error(req, res, "pin_blocked", "pin is blocked by board safety policy");
    details["pin"] = pin;
    details["label"] = policy.label;
    details["reason"] = policy.reason;
    return false;
  }

  bool allowed = false;
  if (str_eq(capability, "digital_in")) {
    allowed = policy.digitalIn;
  } else if (str_eq(capability, "digital_out")) {
    allowed = policy.digitalOut;
  } else if (str_eq(capability, "adc")) {
    allowed = policy.adc;
  } else if (str_eq(capability, "pwm")) {
    allowed = policy.pwm;
  }

  if (!allowed) {
    JsonObject details = reply_error(req, res, "capability_not_allowed", "pin capability is not allowed");
    details["pin"] = pin;
    details["capability"] = capability;
    details["label"] = policy.label;
    return false;
  }

  return true;
}

bool ensure_pwm_channel(JsonVariantConst req,
                        JsonDocument &res,
                        int pin,
                        uint32_t freq,
                        uint8_t resolution,
                        int *channelOut) {
  auto it = g_pwmChannels.find(pin);
  int channel = -1;
  if (it != g_pwmChannels.end()) {
    channel = it->second;
  } else {
    if (g_nextPwmChannel >= kMaxPwmChannels) {
      reply_error(req, res, "pwm_channel_exhausted", "no free PWM channels left");
      return false;
    }
    channel = g_nextPwmChannel++;
    g_pwmChannels[pin] = channel;
    ledcAttachPin(pin, channel);
  }

  double configuredFreq = ledcSetup(channel, freq, resolution);
  if (configuredFreq <= 0) {
    JsonObject details = reply_error(req, res, "pwm_setup_failed", "failed to configure PWM channel");
    details["pin"] = pin;
    details["channel"] = channel;
    details["freq"] = freq;
    details["resolution"] = resolution;
    return false;
  }

  *channelOut = channel;
  return true;
}

uint32_t uart_config_from_fields(int dataBits, char parity, int stopBits, bool *ok) {
  char p = static_cast<char>(toupper(static_cast<unsigned char>(parity)));
  *ok = true;

  if (dataBits == 8 && p == 'N' && stopBits == 1) {
    return SERIAL_8N1;
  }
  if (dataBits == 8 && p == 'N' && stopBits == 2) {
    return SERIAL_8N2;
  }
  if (dataBits == 8 && p == 'E' && stopBits == 1) {
    return SERIAL_8E1;
  }
  if (dataBits == 8 && p == 'O' && stopBits == 1) {
    return SERIAL_8O1;
  }
  if (dataBits == 7 && p == 'N' && stopBits == 1) {
    return SERIAL_7N1;
  }
  if (dataBits == 7 && p == 'E' && stopBits == 1) {
    return SERIAL_7E1;
  }
  if (dataBits == 7 && p == 'O' && stopBits == 1) {
    return SERIAL_7O1;
  }

  *ok = false;
  return SERIAL_8N1;
}

bool ensure_uart_open(JsonVariantConst req, JsonDocument &res) {
  if (!g_uartState.open) {
    reply_error(req, res, "uart_not_open", "UART is not open");
    return false;
  }
  return true;
}

bool validate_uart_pins(JsonVariantConst req, JsonDocument &res, int rxPin, int txPin) {
  if (rxPin == kDefaultUartRxPin && txPin == kDefaultUartTxPin) {
    return true;
  }

  JsonObject details = reply_error(req, res, "unsupported_uart_pins", "requested UART pins are unsupported by this board profile");
  details["rx_pin"] = rxPin;
  details["tx_pin"] = txPin;
  details["supported_rx_pin"] = kDefaultUartRxPin;
  details["supported_tx_pin"] = kDefaultUartTxPin;
  return false;
}

void add_uart_state(JsonObject out) {
  char parityStr[2] = {g_uartState.parity, '\0'};
  out["open"] = g_uartState.open;
  out["baud"] = g_uartState.baud;
  out["rx_pin"] = g_uartState.rxPin;
  out["tx_pin"] = g_uartState.txPin;
  out["data_bits"] = g_uartState.dataBits;
  out["parity"] = parityStr;
  out["stop_bits"] = g_uartState.stopBits;
  out["timeout_ms"] = g_uartState.timeoutMs;
}

String bytes_to_hex(const uint8_t *data, size_t len) {
  static const char *kHex = "0123456789ABCDEF";
  String out;
  out.reserve(len * 2);
  for (size_t i = 0; i < len; ++i) {
    out += kHex[data[i] >> 4];
    out += kHex[data[i] & 0x0F];
  }
  return out;
}

int hex_nibble(char c) {
  if (c >= '0' && c <= '9') {
    return c - '0';
  }
  if (c >= 'A' && c <= 'F') {
    return 10 + (c - 'A');
  }
  if (c >= 'a' && c <= 'f') {
    return 10 + (c - 'a');
  }
  return -1;
}

size_t parse_hex_payload(const String &hex, uint8_t *out, size_t outCap, bool *ok) {
  *ok = false;
  size_t outLen = 0;
  int hi = -1;

  for (size_t i = 0; i < hex.length(); ++i) {
    char c = hex[i];
    if (c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == ':') {
      continue;
    }
    int n = hex_nibble(c);
    if (n < 0) {
      return 0;
    }
    if (hi < 0) {
      hi = n;
    } else {
      if (outLen >= outCap) {
        return 0;
      }
      out[outLen++] = static_cast<uint8_t>((hi << 4) | n);
      hi = -1;
    }
  }

  if (hi >= 0) {
    return 0;
  }

  *ok = true;
  return outLen;
}

String bytes_to_ascii_preview(const uint8_t *data, size_t len) {
  String out;
  out.reserve(len);
  for (size_t i = 0; i < len; ++i) {
    uint8_t c = data[i];
    if (c == '\r' || c == '\n' || c == '\t' || (c >= 32 && c <= 126)) {
      out += static_cast<char>(c);
    } else {
      out += '.';
    }
  }
  return out;
}

void add_policy_snapshot(JsonObject out) {
  JsonArray allowed = out["allowed_pins"].to<JsonArray>();
  JsonObject blocked = out["blocked_pins"].to<JsonObject>();
  JsonObject pinCaps = out["pin_capabilities"].to<JsonObject>();

  for (int pin = 0; pin <= kPolicyMaxPin; ++pin) {
    PinPolicy p = policy_for_pin(pin);
    if (!p.exists) {
      continue;
    }

    JsonObject cap = pinCaps[String(pin)].to<JsonObject>();
    cap["label"] = p.label;
    cap["digital_in"] = p.digitalIn;
    cap["digital_out"] = p.digitalOut;
    cap["adc"] = p.adc;
    cap["pwm"] = p.pwm;

    if (p.blocked) {
      blocked[String(pin)] = p.reason;
    } else {
      allowed.add(pin);
    }
  }

  JsonObject named = out["named_pins"].to<JsonObject>();
  add_named_pins(named);

  JsonObject uartPins = out["uart_pins"].to<JsonObject>();
  uartPins["rx"] = kDefaultUartRxPin;
  uartPins["tx"] = kDefaultUartTxPin;
  uartPins["note"] = "reserved for UART bridge; blocked for gpio_* tools";
}

void handle_single_command(JsonVariantConst req, JsonDocument &res, bool allowBatch);

void handle_batch(JsonVariantConst req, JsonDocument &res) {
  if (!req["ops"].is<JsonArrayConst>()) {
    reply_error(req, res, "missing_ops", "batch requires an ops array");
    return;
  }

  reply_ok(req, res);
  JsonArray out = res["result"].to<JsonArray>();
  bool allOk = true;

  for (JsonVariantConst op : req["ops"].as<JsonArrayConst>()) {
    JsonDocument opRes;
    handle_single_command(op, opRes, false);
    JsonObject item = out.add<JsonObject>();
    item.set(opRes.as<JsonObjectConst>());
    if (!opRes["ok"].as<bool>()) {
      allOk = false;
    }
  }

  if (!allOk) {
    JsonObject error = res["error"].to<JsonObject>();
    error["code"] = "batch_failed";
    error["message"] = "one or more operations failed";
    res["ok"] = false;
  }
}

void handle_single_command(JsonVariantConst req, JsonDocument &res, bool allowBatch) {
  const char *cmd = req["cmd"] | "";

  if (cmd_is(cmd, "ping")) {
    reply_ok(req, res);
    JsonObject result = res["result"].to<JsonObject>();
    result["pong"] = true;
    result["board"] = kBoardId;
    result["chip_model"] = ESP.getChipModel();
    result["chip_revision"] = ESP.getChipRevision();
    result["cpu_mhz"] = ESP.getCpuFreqMHz();
    result["free_heap"] = ESP.getFreeHeap();
    return;
  }

  if (cmd_is(cmd, "info")) {
    reply_ok(req, res);
    JsonObject result = res["result"].to<JsonObject>();
    result["board"] = kBoardId;
    result["board_profile"] = kBoardProfile;
    result["chip_model"] = ESP.getChipModel();
    result["chip_revision"] = ESP.getChipRevision();
    result["cpu_mhz"] = ESP.getCpuFreqMHz();
    result["flash_size"] = ESP.getFlashChipSize();
    result["free_heap"] = ESP.getFreeHeap();
    result["sdk_version"] = ESP.getSdkVersion();
    add_policy_snapshot(result["policy"].to<JsonObject>());
    add_uart_state(result["uart"].to<JsonObject>());

    JsonObject modes = result["pin_modes"].to<JsonObject>();
    for (const auto &kv : g_pinModes) {
      modes[String(kv.first)] = kv.second;
    }
    return;
  }

  if (cmd_is(cmd, "state")) {
    reply_ok(req, res);
    JsonObject result = res["result"].to<JsonObject>();

    JsonObject modes = result["pin_modes"].to<JsonObject>();
    for (const auto &kv : g_pinModes) {
      modes[String(kv.first)] = kv.second;
    }

    JsonObject digital = result["digital"].to<JsonObject>();
    for (const auto &kv : g_lastDigital) {
      digital[String(kv.first)] = kv.second;
    }

    JsonObject pwm = result["pwm"].to<JsonObject>();
    for (const auto &kv : g_pwmStates) {
      JsonObject p = pwm[String(kv.first)].to<JsonObject>();
      p["enabled"] = kv.second.enabled;
      p["freq"] = kv.second.freq;
      p["resolution"] = kv.second.resolution;
      p["value"] = kv.second.value;
    }

    add_policy_snapshot(result["policy"].to<JsonObject>());
    add_uart_state(result["uart"].to<JsonObject>());
    return;
  }

  if (allowBatch && cmd_is(cmd, "batch", "transaction")) {
    handle_batch(req, res);
    return;
  }

  if (cmd_is(cmd, "uart_info")) {
    reply_ok(req, res);
    JsonObject result = res["result"].to<JsonObject>();
    add_uart_state(result);
    result["supported_rx_pin"] = kDefaultUartRxPin;
    result["supported_tx_pin"] = kDefaultUartTxPin;
    return;
  }

  if (cmd_is(cmd, "uart_open")) {
    uint32_t baud = req["baud"] | 115200;
    int rxPin = req["rx_pin"] | kDefaultUartRxPin;
    int txPin = req["tx_pin"] | kDefaultUartTxPin;
    int dataBits = req["data_bits"] | 8;
    int stopBits = req["stop_bits"] | 1;
    const char *parityStr = req["parity"] | "N";
    char parity = parityStr[0];
    uint32_t timeoutMs = req["timeout_ms"] | 20;

    if (baud < 300 || baud > 2000000) {
      JsonObject details = reply_error(req, res, "invalid_uart_baud", "baud must be within 300..2000000");
      details["baud"] = baud;
      return;
    }

    if (!validate_uart_pins(req, res, rxPin, txPin)) {
      return;
    }

    bool configOk = false;
    uint32_t config = uart_config_from_fields(dataBits, parity, stopBits, &configOk);
    if (!configOk) {
      char parityBuf[2] = {static_cast<char>(toupper(static_cast<unsigned char>(parity))), '\0'};
      JsonObject details = reply_error(req, res, "invalid_uart_config", "unsupported UART config");
      details["data_bits"] = dataBits;
      details["parity"] = parityBuf;
      details["stop_bits"] = stopBits;
      return;
    }

    if (g_uartState.open) {
      Serial1.flush();
      Serial1.end();
      delay(10);
    }

    Serial1.begin(baud, config, rxPin, txPin);
    Serial1.setTimeout(timeoutMs);

    g_uartState.open = true;
    g_uartState.baud = baud;
    g_uartState.rxPin = rxPin;
    g_uartState.txPin = txPin;
    g_uartState.dataBits = dataBits;
    g_uartState.parity = static_cast<char>(toupper(static_cast<unsigned char>(parity)));
    g_uartState.stopBits = stopBits;
    g_uartState.timeoutMs = timeoutMs;

    reply_ok(req, res);
    JsonObject result = res["result"].to<JsonObject>();
    add_uart_state(result);
    return;
  }

  if (cmd_is(cmd, "uart_close")) {
    if (g_uartState.open) {
      Serial1.flush();
      Serial1.end();
    }
    g_uartState.open = false;

    reply_ok(req, res);
    JsonObject result = res["result"].to<JsonObject>();
    result["closed"] = true;
    add_uart_state(result["uart"].to<JsonObject>());
    return;
  }

  if (cmd_is(cmd, "uart_write")) {
    if (!ensure_uart_open(req, res)) {
      return;
    }

    bool hasText = req["text"].is<const char *>();
    bool hasHex = req["hex"].is<const char *>();
    if (!hasText && !hasHex) {
      reply_error(req, res, "missing_uart_payload", "uart_write requires text or hex");
      return;
    }

    size_t written = 0;
    if (hasText) {
      String text = req["text"].as<const char *>();
      if (text.length() > kMaxUartWriteBytes) {
        JsonObject details = reply_error(req, res, "uart_payload_too_large", "text payload exceeds write limit");
        details["max_bytes"] = kMaxUartWriteBytes;
        return;
      }
      written += Serial1.write(reinterpret_cast<const uint8_t *>(text.c_str()), text.length());
    }

    if (hasHex) {
      String hex = req["hex"].as<const char *>();
      uint8_t raw[kMaxUartWriteBytes];
      bool parsed = false;
      size_t rawLen = parse_hex_payload(hex, raw, kMaxUartWriteBytes, &parsed);
      if (!parsed) {
        reply_error(req, res, "invalid_uart_hex", "hex payload is malformed or exceeds write limit");
        return;
      }
      written += Serial1.write(raw, rawLen);
    }

    bool appendNewline = req["append_newline"] | false;
    if (appendNewline) {
      written += Serial1.write('\n');
    }

    bool drain = req["drain"] | true;
    if (drain) {
      Serial1.flush();
    }

    reply_ok(req, res);
    JsonObject result = res["result"].to<JsonObject>();
    result["bytes_written"] = written;
    result["drained"] = drain;
    return;
  }

  if (cmd_is(cmd, "uart_read")) {
    if (!ensure_uart_open(req, res)) {
      return;
    }

    size_t maxBytes = req["max_bytes"] | 128;
    if (maxBytes == 0 || maxBytes > kMaxUartReadBytes) {
      JsonObject details = reply_error(req, res, "invalid_uart_read_size", "max_bytes must be in range 1..512");
      details["max_bytes"] = maxBytes;
      return;
    }

    uint32_t timeoutMs = req["timeout_ms"] | g_uartState.timeoutMs;
    uint32_t start = millis();
    while (Serial1.available() <= 0 && (millis() - start) < timeoutMs) {
      delay(1);
    }

    uint8_t buf[kMaxUartReadBytes];
    size_t count = 0;
    while (count < maxBytes && Serial1.available() > 0) {
      int b = Serial1.read();
      if (b >= 0) {
        buf[count++] = static_cast<uint8_t>(b);
      }
    }

    bool truncated = (count >= maxBytes) && (Serial1.available() > 0);
    reply_ok(req, res);
    JsonObject result = res["result"].to<JsonObject>();
    result["bytes"] = count;
    result["text"] = bytes_to_ascii_preview(buf, count);
    result["hex"] = bytes_to_hex(buf, count);
    result["truncated"] = truncated;
    result["remaining_available"] = Serial1.available();
    return;
  }

  if (cmd_is(cmd, "set_mode", "pinMode")) {
    if (!req["pin"].is<int>() || !req["mode"].is<const char *>()) {
      reply_error(req, res, "missing_pin_or_mode", "set_mode requires integer pin and mode string");
      return;
    }

    int pin = req["pin"].as<int>();
    String mode = req["mode"].as<const char *>();
    const char *cap = (mode == "output" || mode == "output_open_drain") ? "digital_out" : "digital_in";
    if (!check_pin_policy(req, res, pin, cap)) {
      return;
    }

    if (!set_pin_mode_hw(pin, mode)) {
      JsonObject details = reply_error(req, res, "invalid_mode", "mode is unsupported by firmware");
      details["mode"] = mode;
      return;
    }

    reply_ok(req, res);
    JsonObject result = res["result"].to<JsonObject>();
    result["pin"] = pin;
    result["mode"] = mode;
    return;
  }

  if (cmd_is(cmd, "write", "digitalWrite")) {
    if (!req["pin"].is<int>() || !req["value"].is<int>()) {
      reply_error(req, res, "missing_pin_or_value", "write requires integer pin and value");
      return;
    }

    int pin = req["pin"].as<int>();
    int value = req["value"].as<int>() ? HIGH : LOW;

    if (!check_pin_policy(req, res, pin, "digital_out") || !ensure_mode_output(req, res, pin)) {
      return;
    }

    digitalWrite(pin, value);
    g_lastDigital[pin] = value == HIGH ? 1 : 0;

    reply_ok(req, res);
    JsonObject result = res["result"].to<JsonObject>();
    result["pin"] = pin;
    result["value"] = g_lastDigital[pin];
    return;
  }

  if (cmd_is(cmd, "digital_write_pulse")) {
    if (!req["pin"].is<int>() || !req["value"].is<int>()) {
      reply_error(req, res, "missing_pin_or_value", "digital_write_pulse requires integer pin and value");
      return;
    }

    int pin = req["pin"].as<int>();
    int highValue = req["value"].as<int>() ? HIGH : LOW;
    uint32_t durationMs = req["duration_ms"] | 100;

    if (!check_pin_policy(req, res, pin, "digital_out") || !ensure_mode_output(req, res, pin)) {
      return;
    }

    int restore = (highValue == HIGH) ? LOW : HIGH;
    if (req["restore"].is<int>()) {
      restore = req["restore"].as<int>() ? HIGH : LOW;
    }

    digitalWrite(pin, highValue);
    delay(durationMs);
    digitalWrite(pin, restore);
    g_lastDigital[pin] = restore == HIGH ? 1 : 0;

    reply_ok(req, res);
    JsonObject result = res["result"].to<JsonObject>();
    result["pin"] = pin;
    result["duration_ms"] = durationMs;
    result["pulse_value"] = highValue == HIGH ? 1 : 0;
    result["final_value"] = g_lastDigital[pin];
    return;
  }

  if (cmd_is(cmd, "read", "digitalRead")) {
    if (!req["pin"].is<int>()) {
      reply_error(req, res, "missing_pin", "read requires integer pin");
      return;
    }

    int pin = req["pin"].as<int>();
    if (!check_pin_policy(req, res, pin, "digital_in")) {
      return;
    }

    int value = digitalRead(pin);
    reply_ok(req, res);
    JsonObject result = res["result"].to<JsonObject>();
    result["pin"] = pin;
    result["value"] = value;
    return;
  }

  if (cmd_is(cmd, "adc_read", "analogRead")) {
    if (!req["pin"].is<int>()) {
      reply_error(req, res, "missing_pin", "adc_read requires integer pin");
      return;
    }

    int pin = req["pin"].as<int>();
    if (!check_pin_policy(req, res, pin, "adc")) {
      return;
    }

    int value = analogRead(pin);
    reply_ok(req, res);
    JsonObject result = res["result"].to<JsonObject>();
    result["pin"] = pin;
    result["value"] = value;
    return;
  }

  if (cmd_is(cmd, "pwm_write", "analogWrite")) {
    if (!req["pin"].is<int>() || !req["value"].is<int>()) {
      reply_error(req, res, "missing_pin_or_value", "pwm_write requires integer pin and value");
      return;
    }

    int pin = req["pin"].as<int>();
    uint32_t value = req["value"].as<uint32_t>();
    uint32_t freq = req["freq"] | 5000;
    uint8_t resolution = req["resolution"] | 8;

    if (!check_pin_policy(req, res, pin, "pwm") || !ensure_mode_output(req, res, pin)) {
      return;
    }

    if (resolution < 1 || resolution > 14) {
      JsonObject details = reply_error(req, res, "invalid_resolution", "resolution must be in range 1..14");
      details["resolution"] = resolution;
      return;
    }

    uint32_t maxValue = (1UL << resolution) - 1;
    if (value > maxValue) {
      JsonObject details = reply_error(req, res, "value_out_of_range", "PWM value exceeds resolution range");
      details["value"] = value;
      details["max_value"] = maxValue;
      return;
    }

    if (freq < 1 || freq > 40000) {
      JsonObject details = reply_error(req, res, "invalid_frequency", "freq must be in range 1..40000");
      details["freq"] = freq;
      return;
    }

    int channel = -1;
    if (!ensure_pwm_channel(req, res, pin, freq, resolution, &channel)) {
      return;
    }

    ledcWrite(channel, value);
    g_pwmStates[pin] = PwmConfig(true, freq, resolution, value);

    reply_ok(req, res);
    JsonObject result = res["result"].to<JsonObject>();
    result["pin"] = pin;
    result["value"] = value;
    result["freq"] = freq;
    result["resolution"] = resolution;
    return;
  }

  JsonObject details = reply_error(req, res, "unknown_command", "command is not supported");
  details["cmd"] = cmd;
}

void handle_line(const String &line) {
  JsonDocument req;
  JsonDocument res;

  DeserializationError err = deserializeJson(req, line);
  if (err) {
    JsonObject details = reply_error(JsonVariantConst(), res, "invalid_json", "unable to parse JSON request");
    details["parse_error"] = err.c_str();
    send_json(res);
    return;
  }

  handle_single_command(req.as<JsonVariantConst>(), res, true);
  send_json(res);
}

void emit_boot_event() {
  JsonDocument boot;
  boot["ok"] = true;
  boot["event"] = "boot";
  JsonObject data = boot["result"].to<JsonObject>();
  data["board"] = kBoardId;
  data["board_profile"] = kBoardProfile;
  data["chip_model"] = ESP.getChipModel();
  add_meta(boot);
  send_json(boot);
}

}  // namespace

void setup() {
  Serial.begin(115200);
  delay(700);
  emit_boot_event();
}

void loop() {
  while (Serial.available() > 0) {
    char c = static_cast<char>(Serial.read());

    if (c == '\n') {
      if (g_overflow) {
        JsonDocument res;
        reply_error(JsonVariantConst(), res, "line_too_long", "input line exceeded 512 bytes");
        send_json(res);
      } else {
        String line = g_inputBuffer;
        line.trim();
        if (line.length() > 0) {
          handle_line(line);
        }
      }
      g_inputBuffer = "";
      g_overflow = false;
      continue;
    }

    if (c == '\r') {
      continue;
    }

    if (!g_overflow) {
      if (g_inputBuffer.length() >= kMaxLineLength) {
        g_overflow = true;
      } else {
        g_inputBuffer += c;
      }
    }
  }
}
