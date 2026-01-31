/* Biospider Control Interface - ESP32-S3 LVGL + ESP-NOW */

#include "waveshare_rgb_lcd_port.h"
#include "lvgl.h"
#include "lvgl_joystick.h"

#include "driver/i2c.h"
#include "esp_err.h"
#include "esp_log.h"
#include "esp_task_wdt.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <string.h>
#include <math.h>

#include "esp_wifi.h"
#include "esp_now.h"
#include "esp_event.h"
#include "nvs_flash.h"
#include "esp_netif.h"
#ifdef CONFIG_BT_ENABLED
#include "esp_bt.h"
#include "esp_bt_main.h"
#include "esp_gap_ble.h"
#endif
#include "gui_guider.h"
#include "events_init.h"
#include "widgets_init.h"
#include "custom.h"

lv_ui guider_ui;
static void init_wifi_espnow(void);
static void bio_send_movement(const char *direction);
static void bio_movement_timer_cb(lv_timer_t *timer);
static void wire_biospider_events_to_demo3_ui(lv_ui *ui);
static void create_terminal_log_widget(lv_ui *ui);
// UI elements
static lv_obj_t *bio_terminal_log = NULL;
static lv_obj_t *bio_speed_slider = NULL;
static lv_obj_t *bio_speed_label = NULL;
static int bio_movement_speed = 75;
static lv_obj_t *bio_rssi_label = NULL;
static int last_rssi_dbm = 0;
static float last_distance_m = 0.0f;
static lv_obj_t *temp_label_bio = NULL;
static lv_obj_t *dist_label_bio = NULL;
static float current_temperature_c = 0.0f;
static float current_distance_cm = 0.0f;
// ESP-NOW peer
static uint8_t peer_mac_biospider[6] = {0xb8, 0xd6, 0x1a, 0xab, 0xd3, 0xbc};
// Connection status
static bool espnow_initialized = false;
static bool wifi_initialized = false;
static bool bluetooth_initialized = false;
static int connected_peers = 0;

// RSSI ping
static uint32_t last_ping_ms = 0;
static const uint32_t ping_interval_ms = 200;
static uint32_t spm_ping_until_ms = 0;
static const float rssi_ref_dbm = -40.0f;
static const float path_loss_n = 2.0f;
static const char *TAG = "GUI CONTROL";

// Log buffer
#define MAX_LOG_LINES 20
#define MAX_LOG_LINE_LEN 80
static char log_buffer[MAX_LOG_LINES][MAX_LOG_LINE_LEN];
static int log_index = 0;

// Update terminal log (yellow for warnings, green for info)
static void update_terminal_log(const char *message) {
    char colored_msg[MAX_LOG_LINE_LEN];
    if (message[0] == 'W' || message[0] == '!')
        snprintf(colored_msg, MAX_LOG_LINE_LEN, "#FFFF00 %s#", message);
    else
        snprintf(colored_msg, MAX_LOG_LINE_LEN, "#00FF00 %s#", message);

    snprintf(log_buffer[log_index], MAX_LOG_LINE_LEN, "%s", colored_msg);
    log_index = (log_index + 1) % MAX_LOG_LINES;

    static char display_text[MAX_LOG_LINES * MAX_LOG_LINE_LEN];
    display_text[0] = '\0';
    int lines_to_show = 10;
    for (int i = 0; i < lines_to_show; i++) {
        int idx = (log_index + MAX_LOG_LINES - lines_to_show + i) % MAX_LOG_LINES;
        if (log_buffer[idx][0] != '\0') {
            strncat(display_text, log_buffer[idx], MAX_LOG_LINE_LEN);
            strncat(display_text, "\n", 2);
        }
    }
    if (bio_terminal_log && lvgl_port_lock(10)) {
        lv_label_set_text_static(bio_terminal_log, display_text);
        lvgl_port_unlock();
    }
}

static float fahrenheit_to_celsius(float temp_f) {
    return (temp_f - 32.0f) * 5.0f / 9.0f;
}
static void update_temperature_display(float temp_celsius) {
    current_temperature_c = temp_celsius;
    if (lvgl_port_lock(10)) {
        char temp_str[16];
        snprintf(temp_str, sizeof(temp_str), "%.1f", temp_celsius);
        lv_table_set_cell_value(guider_ui.screen_telementry, 2, 1, temp_str);
        lvgl_port_unlock();
    }
    ESP_LOGI(TAG, "Temp: %.1f°C", temp_celsius);
}
static void update_distance_display(float distance_cm) {
    current_distance_cm = distance_cm;
    if (lvgl_port_lock(10)) {
        char dist_str[16];
        snprintf(dist_str, sizeof(dist_str), distance_cm < 0 ? "--" : "%.0f", distance_cm);
        lv_table_set_cell_value(guider_ui.screen_telementry, 1, 1, dist_str);
        lvgl_port_unlock();
    }
    ESP_LOGI(TAG, "Dist: %.1f cm", distance_cm);
}


// Send movement command to Biospider robot
// Sends a JSON command like: {"cmd":"MOVE","dir":"UP","speed":75}
static void bio_send_movement(const char *direction) {
    // Send JSON command with speed: {"cmd":"MOVE","dir":"UP","speed":75}
    char msg[128];
    snprintf(msg, sizeof(msg),
             "{\"cmd\":\"MOVE\",\"dir\":\"%s\",\"speed\":%d}",
             direction, bio_movement_speed);

    esp_err_t result = esp_now_send(peer_mac_biospider, (uint8_t *)msg, strlen(msg));
    if (result == ESP_OK) {
        ESP_LOGI(TAG, "Movement command sent: %s @ %d%%", direction, bio_movement_speed);
    } else {
        ESP_LOGW(TAG, "Movement command failed: %s", direction);
    }
}

// Timer for periodic RSSI ping during SPM mode
static void bio_movement_timer_cb(lv_timer_t *timer) {
    uint32_t now = (uint32_t)(esp_timer_get_time() / 1000ULL);
    if (now < spm_ping_until_ms && now - last_ping_ms > ping_interval_ms) {
        esp_now_send(peer_mac_biospider, (uint8_t *)"PING", 4);
        last_ping_ms = now;
    }
}

// Directional buttons
static void bio_up_btn_cb(lv_event_t *e) {
    if (lv_event_get_code(e) == LV_EVENT_PRESSED) { update_terminal_log("I UP"); bio_send_movement("UP"); }
}
static void bio_down_btn_cb(lv_event_t *e) {
    if (lv_event_get_code(e) == LV_EVENT_PRESSED) { update_terminal_log("I DOWN"); bio_send_movement("DOWN"); }
}
static void bio_left_btn_cb(lv_event_t *e) {
    if (lv_event_get_code(e) == LV_EVENT_PRESSED) { update_terminal_log("I LEFT"); bio_send_movement("LEFT"); }
}
static void bio_right_btn_cb(lv_event_t *e) {
    if (lv_event_get_code(e) == LV_EVENT_PRESSED) { update_terminal_log("I RIGHT"); bio_send_movement("RIGHT"); }
}

// Emergency stop
static void bio_emergency_stop_cb(lv_event_t *e) {
    esp_err_t result = esp_now_send(peer_mac_biospider, (uint8_t *)"STOP", 4);
    ESP_LOGW(TAG, "BIOSPIDER EMERGENCY STOP!");
    update_terminal_log(result == ESP_OK ? "!!! E-STOP sent !!!" : "!!! E-STOP FAILED !!!");
}

// Preset action callbacks (pre-programmed robot movements)

static void bio_scan_cb(lv_event_t * e) {
    const char *msg = "SCAN";
    esp_err_t result = esp_now_send(peer_mac_biospider, (uint8_t *)msg, strlen(msg));
    if (result == ESP_OK) {
        update_terminal_log("I SCAN sent");
        ESP_LOGI(TAG, "SCAN command sent to Biospider");
    } else {
        update_terminal_log("E SCAN send failed");
    }
}

static void bio_moonwalk_cb(lv_event_t * e) {
    const char *msg = "MOONWALK";
    esp_err_t result = esp_now_send(peer_mac_biospider, (uint8_t *)msg, strlen(msg));
    if (result == ESP_OK) {
        update_terminal_log("I MOONWALK sent");
        ESP_LOGI(TAG, "MOONWALK command sent to Biospider");
    } else {
        update_terminal_log("E MOONWALK send failed");
    }
}

static void bio_spm_cb(lv_event_t * e) {
    const char *msg = "SPM";
    esp_err_t result = esp_now_send(peer_mac_biospider, (uint8_t *)msg, strlen(msg));
    if (result == ESP_OK) {
        update_terminal_log("I FarFromHome command sent");
        ESP_LOGI(TAG, "FarFromHome (Search-Patrol-Monitor) command sent");

        // Enable 15 seconds of ping for RSSI sampling
        spm_ping_until_ms = (uint32_t)(esp_timer_get_time() / 1000ULL) + 15000;
        last_ping_ms = 0;  // Force immediate ping
    } else {
        update_terminal_log("E FarFromHome send failed");
    }
}

static void bio_trot_cb(lv_event_t * e) {
    const char *msg = "TROT";
    esp_err_t result = esp_now_send(peer_mac_biospider, (uint8_t *)msg, strlen(msg));
    if (result == ESP_OK) {
        update_terminal_log("I TROT gait sent");
        ESP_LOGI(TAG, "TROT command sent to Biospider (advanced gait from demo.py)");
    } else {
        update_terminal_log("E TROT send failed");
    }
}

// Speed slider
static void bio_speed_slider_cb(lv_event_t *e) {
    bio_movement_speed = lv_slider_get_value(lv_event_get_target(e));
    if (bio_speed_label) {
        char speed_text[32];
        snprintf(speed_text, sizeof(speed_text), "SPEED: %d%%", bio_movement_speed);
        lv_label_set_text(bio_speed_label, speed_text);
    }
    ESP_LOGI(TAG, "Speed: %d%%", bio_movement_speed);
    char log_msg[64];
    snprintf(log_msg, sizeof(log_msg), "I Speed: %d%%", bio_movement_speed);
    update_terminal_log(log_msg);
}

// Button matrix handler
static void bio_btnmatrix_cb(lv_event_t *e) {
    uint32_t id = lv_btnmatrix_get_selected_btn(lv_event_get_target(e));
    switch (id) {
        case 0: bio_trot_cb(e); break;
        case 1: bio_scan_cb(e); break;
        case 2: bio_moonwalk_cb(e); break;
        case 3: bio_spm_cb(e); break;
        default: break;
    }
}

// Terminal widget (black bg, green text)
static void create_terminal_log_widget(lv_ui *ui) {
    lv_obj_add_flag(ui->screen_msgbox_1, LV_OBJ_FLAG_HIDDEN);
    lv_obj_t *cont = lv_obj_create(ui->screen);
    lv_obj_set_pos(cont, 546, 3);
    lv_obj_set_size(cont, 251, 163);
    lv_obj_set_style_bg_color(cont, lv_color_hex(0x000000), 0);
    lv_obj_set_style_bg_opa(cont, 255, 0);
    lv_obj_set_style_border_width(cont, 2, 0);
    lv_obj_set_style_border_color(cont, lv_color_hex(0x1A4D2E), 0);
    lv_obj_set_style_border_opa(cont, 100, 0);
    lv_obj_set_style_radius(cont, 0, 0);
    lv_obj_set_style_pad_all(cont, 8, 0);

    bio_terminal_log = lv_label_create(cont);
    lv_obj_set_size(bio_terminal_log, LV_PCT(100), LV_PCT(100));
    lv_obj_align(bio_terminal_log, LV_ALIGN_TOP_LEFT, 0, 0);
    lv_obj_set_style_text_color(bio_terminal_log, lv_color_hex(0x00FF00), 0);
    lv_obj_set_style_text_font(bio_terminal_log, &lv_font_montserratMedium_12, 0);
    lv_obj_set_style_text_opa(bio_terminal_log, 255, 0);
    lv_label_set_recolor(bio_terminal_log, true);
    lv_label_set_long_mode(bio_terminal_log, LV_LABEL_LONG_SCROLL_CIRCULAR);
    lv_label_set_text(bio_terminal_log, "#00FF00 System Ready#\n");
}

// Wire events to UI elements
static void wire_biospider_events_to_demo3_ui(lv_ui *ui) {
    lv_obj_add_event_cb(ui->screen_Spider_function_control, bio_btnmatrix_cb, LV_EVENT_CLICKED, NULL);
    lv_obj_add_event_cb(ui->screen_imgbtn_2, bio_up_btn_cb, LV_EVENT_PRESSED, NULL);
    lv_obj_add_event_cb(ui->screen_imgbtn_3, bio_down_btn_cb, LV_EVENT_PRESSED, NULL);
    lv_obj_add_event_cb(ui->screen_imgbtn_4, bio_left_btn_cb, LV_EVENT_PRESSED, NULL);
    lv_obj_add_event_cb(ui->screen_imgbtn_5, bio_right_btn_cb, LV_EVENT_PRESSED, NULL);
    lv_obj_add_event_cb(ui->screen_imgbtn_6, bio_emergency_stop_cb, LV_EVENT_CLICKED, NULL);
    lv_obj_add_event_cb(ui->screen_speedcontrol, bio_speed_slider_cb, LV_EVENT_VALUE_CHANGED, NULL);
    bio_speed_slider = ui->screen_speedcontrol;
}


// ESP-NOW callbacks (ESP-IDF v5.5.2 API)
static void espnow_send_cb(const wifi_tx_info_t *tx_info, esp_now_send_status_t status) {
    // Send callback - status checked silently to reduce log noise
    (void)status; // Unused
}

static float estimate_distance_from_rssi(int rssi_dbm) {
    // d = 10 ^ ((RSSI - A) / (10 * n))
    return powf(10.0f, ((float)rssi_dbm - rssi_ref_dbm) / (10.0f * path_loss_n));
}

static void espnow_recv_cb(const esp_now_recv_info_t *recv_info, const uint8_t *data, int len) {
    ESP_LOGI(TAG, "ESP-NOW: Received %d bytes from %02x:%02x:%02x:%02x:%02x:%02x",
             len, recv_info->src_addr[0], recv_info->src_addr[1], recv_info->src_addr[2],
             recv_info->src_addr[3], recv_info->src_addr[4], recv_info->src_addr[5]);

    // Capture RSSI and estimate distance
    int rssi = recv_info->rx_ctrl->rssi;
    float dist_m = estimate_distance_from_rssi(rssi);

    // Update global RSSI/distance for display
    last_rssi_dbm = rssi;
    last_distance_m = dist_m;

    // Update RSSI display in sensor panel
    if (bio_rssi_label) {
        char rssi_text[32];
        snprintf(rssi_text, sizeof(rssi_text), "%d dBm\n~%.2f m", rssi, dist_m);
        lv_label_set_text(bio_rssi_label, rssi_text);
    }

    char log_msg[180];
    snprintf(log_msg, sizeof(log_msg), "I RSSI: %d dBm @ ~%.2f m", rssi, dist_m);
    update_terminal_log(log_msg);
    ESP_LOGI(TAG, "RSSI %d dBm, est distance %.2f m", rssi, dist_m);

    // Create a null-terminated string from received data (limit to 100 chars for safety)
    char recv_data[101];
    int copy_len = (len < 100) ? len : 100;
    memcpy(recv_data, data, copy_len);
    recv_data[copy_len] = '\0';

    // All ESP-NOW messages are from Biospider (5DOF arm disabled)
    // Display received data in System Log (larger buffer to prevent truncation)
    // Reuse log_msg buffer below

    // Parse JSON data from slave: {"temperature": 133.0, "distance": 16.7, "status": "OBSTACLE", ...}
    char *temp_ptr = strstr(recv_data, "\"temperature\":");
    char *dist_ptr = strstr(recv_data, "\"distance\":");
    char *status_ptr = strstr(recv_data, "\"status\":");

    // Parse and update temperature
    if (temp_ptr != NULL) {
        float temp_fahrenheit = 0.0f;
        if (sscanf(temp_ptr, "\"temperature\": %f", &temp_fahrenheit) == 1 ||
            sscanf(temp_ptr, "\"temperature\":%f", &temp_fahrenheit) == 1) {
            // Convert F to C and update display
            float temp_celsius = fahrenheit_to_celsius(temp_fahrenheit);
            update_temperature_display(temp_celsius);
            ESP_LOGI(TAG, "Temperature: %.1f°F = %.1f°C", temp_fahrenheit, temp_celsius);
        }
    }

    // Parse and update distance
    if (dist_ptr != NULL) {
        float distance = 0.0f;
        if (sscanf(dist_ptr, "\"distance\": %f", &distance) == 1 ||
            sscanf(dist_ptr, "\"distance\":%f", &distance) == 1) {
            update_distance_display(distance);
            ESP_LOGI(TAG, "Distance: %.1f cm", distance);
        }
    }

    // Parse and display status
    if (status_ptr != NULL) {
        char status[32] = {0};
        if (sscanf(status_ptr, "\"status\": \"%31[^\"]\"", status) == 1 ||
            sscanf(status_ptr, "\"status\":\"%31[^\"]\"", status) == 1) {
            snprintf(log_msg, sizeof(log_msg), "I Status: %s", status);
            update_terminal_log(log_msg);
            ESP_LOGI(TAG, "Status: %s", status);
        }
    }

    // Check for specific data patterns and format accordingly
    if (strstr(recv_data, "RANGE:") != NULL) {
        // Sensor range data: "RANGE:123cm" or "RANGE:1.23m"
        snprintf(log_msg, sizeof(log_msg), "I Sensor Range: %s", recv_data + 6);
        update_terminal_log(log_msg);
    } else if (strstr(recv_data, "TEMP:") != NULL) {
        // Temperature data in simple format: "TEMP:25.5C"
        // Parse and update temperature display (don't log to System Log)
        float temp_c = 0.0f;
        if (sscanf(recv_data, "TEMP:%f", &temp_c) == 1) {
            update_temperature_display(temp_c);
            ESP_LOGI(TAG, "Temperature: %.1f°C", temp_c);
        }
    } else if (strstr(recv_data, "ACK") != NULL) {
        // Acknowledgment from slave
        snprintf(log_msg, sizeof(log_msg), "I ACK: %s", recv_data);
        update_terminal_log(log_msg);
    } else if (strstr(recv_data, "STATUS:") != NULL) {
        // Status message
        snprintf(log_msg, sizeof(log_msg), "I %s", recv_data + 7);
        update_terminal_log(log_msg);
    } else if (strstr(recv_data, "distance") == NULL && strstr(recv_data, "temperature") == NULL) {
        // Generic data display (skip full JSON to avoid clutter)
        if (recv_data[0] != '{') {  // Don't log raw JSON
            snprintf(log_msg, sizeof(log_msg), "I RX: %s", recv_data);
            update_terminal_log(log_msg);
        }
    }

    ESP_LOGI(TAG, "Biospider data: %s", recv_data);
}

// Initialize ESP-NOW (WiFi radio without network connection)
static void init_wifi_espnow(void) {
    // Initialize NVS
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // Initialize network interface (required for WiFi radio)
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());

    // Initialize WiFi in STA mode (for ESP-NOW - no network connection needed)
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    ESP_ERROR_CHECK(esp_wifi_start());

    // Set WiFi channel to 1 for ESP-NOW compatibility with MicroPython devices
    ESP_ERROR_CHECK(esp_wifi_set_channel(1, WIFI_SECOND_CHAN_NONE));
    ESP_LOGI(TAG, "WiFi channel set to 1 ");

    // Get and display this device's MAC address for slave configuration
    uint8_t mac[6];
    esp_wifi_get_mac(WIFI_IF_STA, mac);
    ESP_LOGI(TAG, "=================================================");
    ESP_LOGI(TAG, " Master MAC Address: %02x:%02x:%02x:%02x:%02x:%02x",
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    ESP_LOGI(TAG, "Configure this address on slave devices");
    ESP_LOGI(TAG, "=================================================");

    wifi_initialized = true;  // Mark WiFi as initialized

    // Initialize ESP-NOW
    ESP_ERROR_CHECK(esp_now_init());
    ESP_ERROR_CHECK(esp_now_register_send_cb(espnow_send_cb));
    ESP_ERROR_CHECK(esp_now_register_recv_cb(espnow_recv_cb));

    // Configure ESP-NOW peer
    esp_now_peer_info_t peer_info = {};
    peer_info.channel = 1;  // Channel 1 for ESP-NOW
    peer_info.ifidx = WIFI_IF_STA;
    peer_info.encrypt = false;

    // Add Biospider peer (ESP32 - ESP-NOW works reliably)
    memcpy(peer_info.peer_addr, peer_mac_biospider, 6);
    if (esp_now_add_peer(&peer_info) == ESP_OK) {
        connected_peers++;
        ESP_LOGI(TAG, "Biospider peer added (MAC: %02x:%02x:%02x:%02x:%02x:%02x)",
                 peer_mac_biospider[0], peer_mac_biospider[1], peer_mac_biospider[2],
                 peer_mac_biospider[3], peer_mac_biospider[4], peer_mac_biospider[5]);
    }

    espnow_initialized = true;
    ESP_LOGI(TAG, "ESP-NOW initialized with %d peer(s)", connected_peers);
}

// Initialize NVS (called once at startup)
static void init_nvs(void) {
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);
}

// Initialize WiFi radio (for ESP-NOW or WiFi AP connection)
static esp_err_t init_wifi_radio(void) {
    if (wifi_initialized) {
        ESP_LOGW(TAG, "WiFi already initialized");
        return ESP_OK;
    }

    // Initialize network interface (required for WiFi radio)
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());

    // Initialize WiFi in STA mode
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    esp_err_t ret = esp_wifi_init(&cfg);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "WiFi init failed: %s", esp_err_to_name(ret));
        return ret;
    }

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    ESP_ERROR_CHECK(esp_wifi_start());

    // Set WiFi channel to 1 for ESP-NOW compatibility
    ESP_ERROR_CHECK(esp_wifi_set_channel(1, WIFI_SECOND_CHAN_NONE));

    // Get and display MAC address
    uint8_t mac[6];
    esp_wifi_get_mac(WIFI_IF_STA, mac);
    ESP_LOGI(TAG, "WiFi radio initialized. MAC: %02x:%02x:%02x:%02x:%02x:%02x",
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);

    wifi_initialized = true;
    return ESP_OK;
}

// Deinitialize WiFi radio
static esp_err_t deinit_wifi_radio(void) {
    if (!wifi_initialized) {
        ESP_LOGW(TAG, "WiFi not initialized");
        return ESP_OK;
    }

    // Deinit ESP-NOW first if it's running
    if (espnow_initialized) {
        ESP_LOGI(TAG, "Deinitializing ESP-NOW before WiFi...");
        esp_now_deinit();
        espnow_initialized = false;
        connected_peers = 0;
    }

    esp_err_t ret = esp_wifi_stop();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "WiFi stop failed: %s", esp_err_to_name(ret));
        return ret;
    }

    ret = esp_wifi_deinit();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "WiFi deinit failed: %s", esp_err_to_name(ret));
        return ret;
    }

    wifi_initialized = false;
    ESP_LOGI(TAG, "WiFi radio deinitialized");
    return ESP_OK;
}

#ifdef CONFIG_BT_ENABLED
// Initialize Bluetooth
static esp_err_t init_bluetooth(void) {
    if (bluetooth_initialized) {
        ESP_LOGW(TAG, "Bluetooth already initialized");
        return ESP_OK;
    }

    ESP_LOGI(TAG, "Initializing Bluetooth...");

    // Release classic BT memory (we only need BLE)
    esp_err_t ret = esp_bt_controller_mem_release(ESP_BT_MODE_CLASSIC_BT);
    if (ret != ESP_OK) {
        ESP_LOGW(TAG, "BT controller mem release failed: %s", esp_err_to_name(ret));
    }

    // Initialize BT controller
    esp_bt_controller_config_t bt_cfg = BT_CONTROLLER_INIT_CONFIG_DEFAULT();
    ret = esp_bt_controller_init(&bt_cfg);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "BT controller init failed: %s", esp_err_to_name(ret));
        return ret;
    }

    // Enable BLE mode
    ret = esp_bt_controller_enable(ESP_BT_MODE_BLE);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "BT controller enable failed: %s", esp_err_to_name(ret));
        return ret;
    }

    // Initialize Bluedroid stack
    ret = esp_bluedroid_init();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Bluedroid init failed: %s", esp_err_to_name(ret));
        return ret;
    }

    ret = esp_bluedroid_enable();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Bluedroid enable failed: %s", esp_err_to_name(ret));
        return ret;
    }

    bluetooth_initialized = true;
    ESP_LOGI(TAG, "Bluetooth initialized successfully");
    return ESP_OK;
}

// Deinitialize Bluetooth
static esp_err_t deinit_bluetooth(void) {
    if (!bluetooth_initialized) {
        ESP_LOGW(TAG, "Bluetooth not initialized");
        return ESP_OK;
    }

    ESP_LOGI(TAG, "Deinitializing Bluetooth...");

    esp_err_t ret = esp_bluedroid_disable();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Bluedroid disable failed: %s", esp_err_to_name(ret));
    }

    ret = esp_bluedroid_deinit();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Bluedroid deinit failed: %s", esp_err_to_name(ret));
    }

    ret = esp_bt_controller_disable();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "BT controller disable failed: %s", esp_err_to_name(ret));
    }

    ret = esp_bt_controller_deinit();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "BT controller deinit failed: %s", esp_err_to_name(ret));
    }

    bluetooth_initialized = false;
    ESP_LOGI(TAG, "Bluetooth deinitialized");
    return ESP_OK;
}
#endif // CONFIG_BT_ENABLED



void app_main()
{
    ESP_LOGI(TAG, "Starting 47HM's Performance Control Interface...");

    // Feed watchdog during initialization to prevent timeout
    esp_task_wdt_reset();

    // Initialize WiFi and ESP-NOW automatically (ESP-NOW auto-starts for robot control)
    // Bluetooth remains user-controlled via toggle switch
    ESP_LOGI(TAG, "Initializing WiFi and ESP-NOW...");
    init_wifi_espnow();

    ESP_LOGI(TAG, "Initializing display hardware (this may take a few seconds)...");

    // Feed watchdog before long initialization
    esp_task_wdt_reset();

    // Initialize the Waveshare ESP32-S3 RGB LCD with working configuration
    waveshare_esp32_s3_rgb_lcd_init();

    // Feed watchdog after display init
    esp_task_wdt_reset();
    ESP_LOGI(TAG, "Hello, Minh day...");

    // Lock the mutex due to the LVGL APIs are not thread-safe
    if (lvgl_port_lock(-1)) {
        // Initialize SquareLine Studio GUI (demo3 - single Biospider control screen)
        setup_ui(&guider_ui);

        // Wire Biospider event handlers to demo3 UI elements
        wire_biospider_events_to_demo3_ui(&guider_ui);

        // Create custom terminal log widget
        create_terminal_log_widget(&guider_ui);

        // Initialize events and custom code
        events_init(&guider_ui);
        custom_init(&guider_ui);

        // Slow down the animation - must be done AFTER init
        // Stop animation, set new duration, restart
        lv_animimg_start(guider_ui.screen_animimg_1);
        lv_animimg_set_duration(guider_ui.screen_animimg_1, 4000);  // 10 seconds total
         lv_animimg_start(guider_ui.screen_animimg_1);
        ESP_LOGI(TAG, "Animation speed set to 10 seconds per cycle");

        // Screen is already loaded by setup_ui (guider_ui.screen)
        // lv_scr_load(guider_ui.screen);  // Not needed - setup_ui already loads it

        // Create LVGL timer for Biospider continuous movement and SPM ping (100ms interval)
        lv_timer_create(bio_movement_timer_cb, 100, NULL);

        lvgl_port_unlock();
    }

    ESP_LOGI(TAG, "PSD check completed!");
}
