/*
* Copyright 2026 NXP
* NXP Proprietary. This software is owned or controlled by NXP and may only be used strictly in
* accordance with the applicable license terms. By expressly accepting such terms or by downloading, installing,
* activating and/or otherwise using the software, you are agreeing that you have read, and that you agree to
* comply with and are bound by, such license terms.  If you do not agree to be bound by the applicable license
* terms, then you may not retain, install, activate or otherwise use the software.
*/

#ifndef GUI_GUIDER_H
#define GUI_GUIDER_H
#ifdef __cplusplus
extern "C" {
#endif

#include "lvgl.h"

typedef struct
{
  
	lv_obj_t *screen;
	bool screen_del;
	lv_obj_t *screen_Spider_function_control;
	lv_obj_t *screen_imgbtn_2;
	lv_obj_t *screen_imgbtn_2_label;
	lv_obj_t *screen_imgbtn_3;
	lv_obj_t *screen_imgbtn_3_label;
	lv_obj_t *screen_imgbtn_4;
	lv_obj_t *screen_imgbtn_4_label;
	lv_obj_t *screen_animimg_1;
	lv_obj_t *screen_imgbtn_5;
	lv_obj_t *screen_imgbtn_5_label;
	lv_obj_t *screen_imgbtn_6;
	lv_obj_t *screen_imgbtn_6_label;
	lv_obj_t *screen_telementry;
	lv_obj_t *screen_speedcontrol;
	lv_obj_t *screen_label_1;
	lv_obj_t *screen_img_1;
	lv_obj_t *screen_msgbox_1;
}lv_ui;

typedef void (*ui_setup_scr_t)(lv_ui * ui);

void ui_init_style(lv_style_t * style);

void ui_load_scr_animation(lv_ui *ui, lv_obj_t ** new_scr, bool new_scr_del, bool * old_scr_del, ui_setup_scr_t setup_scr,
                           lv_scr_load_anim_t anim_type, uint32_t time, uint32_t delay, bool is_clean, bool auto_del);

void ui_animation(void * var, int32_t duration, int32_t delay, int32_t start_value, int32_t end_value, lv_anim_path_cb_t path_cb,
                       uint16_t repeat_cnt, uint32_t repeat_delay, uint32_t playback_time, uint32_t playback_delay,
                       lv_anim_exec_xcb_t exec_cb, lv_anim_start_cb_t start_cb, lv_anim_ready_cb_t ready_cb, lv_anim_deleted_cb_t deleted_cb);


void init_scr_del_flag(lv_ui *ui);

void setup_ui(lv_ui *ui);

void init_keyboard(lv_ui *ui);

extern lv_ui guider_ui;


void setup_scr_screen(lv_ui *ui);

// LV_IMG_DECLARE(_white_800x480);  // Removed to save 27MB flash space
LV_IMG_DECLARE(_realesearrow_UP_alpha_83x67);
LV_IMG_DECLARE(_animationarrow_UP_0_alpha_83x67);
LV_IMG_DECLARE(_realesearrow_DOWN_alpha_76x70);
LV_IMG_DECLARE(_animationarrow_DOWN_0_alpha_76x70);
LV_IMG_DECLARE(_realesearrow_LEFT_alpha_68x80);
LV_IMG_DECLARE(_animationarrow_LEFT_0_alpha_68x80);
#include "extra/widgets/animimg/lv_animimg.h"
LV_IMG_DECLARE(screen_animimg_1biomove3_00);
LV_IMG_DECLARE(screen_animimg_1biomove3_01);
LV_IMG_DECLARE(screen_animimg_1biomove3_02);
LV_IMG_DECLARE(screen_animimg_1biomove3_03);
LV_IMG_DECLARE(screen_animimg_1biomove3_04);
LV_IMG_DECLARE(screen_animimg_1biomove3_05);
LV_IMG_DECLARE(screen_animimg_1biomove3_06);
LV_IMG_DECLARE(screen_animimg_1biomove3_07);
LV_IMG_DECLARE(screen_animimg_1biomove3_08);
LV_IMG_DECLARE(screen_animimg_1biomove3_09);
LV_IMG_DECLARE(screen_animimg_1biomove3_10);
LV_IMG_DECLARE(screen_animimg_1biomove3_11);
LV_IMG_DECLARE(screen_animimg_1biomove3_12);
LV_IMG_DECLARE(screen_animimg_1biomove3_13);
LV_IMG_DECLARE(screen_animimg_1biomove3_14);
LV_IMG_DECLARE(screen_animimg_1biomove3_15);
LV_IMG_DECLARE(screen_animimg_1biomove3_16);
LV_IMG_DECLARE(screen_animimg_1biomove3_17);
LV_IMG_DECLARE(screen_animimg_1biomove3_18);
LV_IMG_DECLARE(screen_animimg_1biomove3_19);
LV_IMG_DECLARE(screen_animimg_1biomove3_20);
LV_IMG_DECLARE(screen_animimg_1biomove3_21);
LV_IMG_DECLARE(screen_animimg_1biomove3_22);
LV_IMG_DECLARE(screen_animimg_1biomove3_23);
LV_IMG_DECLARE(screen_animimg_1biomove3_24);
LV_IMG_DECLARE(screen_animimg_1biomove3_25);
LV_IMG_DECLARE(screen_animimg_1biomove3_26);
LV_IMG_DECLARE(screen_animimg_1biomove3_27);
LV_IMG_DECLARE(screen_animimg_1biomove3_28);
LV_IMG_DECLARE(screen_animimg_1biomove3_29);
LV_IMG_DECLARE(screen_animimg_1biomove3_30);
LV_IMG_DECLARE(screen_animimg_1biomove3_31);
LV_IMG_DECLARE(screen_animimg_1biomove3_32);
LV_IMG_DECLARE(screen_animimg_1biomove3_33);
LV_IMG_DECLARE(screen_animimg_1biomove3_34);
LV_IMG_DECLARE(screen_animimg_1biomove3_35);
LV_IMG_DECLARE(screen_animimg_1biomove3_36);
LV_IMG_DECLARE(screen_animimg_1biomove3_37);
LV_IMG_DECLARE(screen_animimg_1biomove3_38);
LV_IMG_DECLARE(screen_animimg_1biomove3_39);
LV_IMG_DECLARE(screen_animimg_1biomove3_40);
LV_IMG_DECLARE(screen_animimg_1biomove3_41);
LV_IMG_DECLARE(screen_animimg_1biomove3_42);
LV_IMG_DECLARE(screen_animimg_1biomove3_43);
LV_IMG_DECLARE(screen_animimg_1biomove3_44);
LV_IMG_DECLARE(screen_animimg_1biomove3_45);
LV_IMG_DECLARE(screen_animimg_1biomove3_46);
LV_IMG_DECLARE(screen_animimg_1biomove3_47);
LV_IMG_DECLARE(screen_animimg_1biomove3_48);
LV_IMG_DECLARE(screen_animimg_1biomove3_49);
LV_IMG_DECLARE(screen_animimg_1biomove3_50);
LV_IMG_DECLARE(screen_animimg_1biomove3_51);
LV_IMG_DECLARE(screen_animimg_1biomove3_52);
LV_IMG_DECLARE(screen_animimg_1biomove3_53);
LV_IMG_DECLARE(screen_animimg_1biomove3_54);
LV_IMG_DECLARE(screen_animimg_1biomove3_55);
LV_IMG_DECLARE(screen_animimg_1biomove3_56);
LV_IMG_DECLARE(screen_animimg_1biomove3_57);
LV_IMG_DECLARE(screen_animimg_1biomove3_58);
LV_IMG_DECLARE(screen_animimg_1biomove3_59);
LV_IMG_DECLARE(screen_animimg_1biomove3_60);
LV_IMG_DECLARE(screen_animimg_1biomove3_61);
LV_IMG_DECLARE(screen_animimg_1biomove3_62);
LV_IMG_DECLARE(screen_animimg_1biomove3_63);
LV_IMG_DECLARE(screen_animimg_1biomove3_64);
LV_IMG_DECLARE(screen_animimg_1biomove3_65);
LV_IMG_DECLARE(screen_animimg_1biomove3_66);
LV_IMG_DECLARE(screen_animimg_1biomove3_67);
LV_IMG_DECLARE(screen_animimg_1biomove3_68);
LV_IMG_DECLARE(screen_animimg_1biomove3_69);
LV_IMG_DECLARE(screen_animimg_1biomove3_70);
LV_IMG_DECLARE(screen_animimg_1biomove3_71);
LV_IMG_DECLARE(screen_animimg_1biomove3_72);
LV_IMG_DECLARE(screen_animimg_1biomove3_73);
LV_IMG_DECLARE(screen_animimg_1biomove3_74);
LV_IMG_DECLARE(_realesearrow_85x80);
LV_IMG_DECLARE(_animationarrow_00_85x80);
LV_IMG_DECLARE(_estop1_alpha_100x93);
LV_IMG_DECLARE(_estop_pressed_alpha_100x93);
LV_IMG_DECLARE(_BIOLOGO2_alpha_230x121);

LV_FONT_DECLARE(lv_font_Alatsi_Regular_20)
LV_FONT_DECLARE(lv_font_montserratMedium_12)
LV_FONT_DECLARE(lv_font_arial_14)
LV_FONT_DECLARE(lv_font_Alatsi_Regular_16)
LV_FONT_DECLARE(lv_font_montserratMedium_15)


#ifdef __cplusplus
}
#endif
#endif
