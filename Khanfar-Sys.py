import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import cv2
from PIL import Image, ImageTk
import logging
from typing import Optional, Dict, List
from config import Config
from detection_system import DetectionSystem
from sounds import SoundManager
from cleanup_manager import CleanupManager
from telegram_bot import TelegramBot
from rtsp_manager import RTSPManager
import os
import time
from translations import TRANSLATIONS
from hardware_info import check_activation
from activation_gui import ActivationDialog
from datetime import datetime
from updater import Updater
import threading
from web_server import ServerThread
import numpy as np
import socket
import json
from remote_updates import RemoteUpdates
import re
from tkinter.simpledialog import askstring
from subprocess import Popen, PIPE

logger = logging.getLogger(__name__)

class PlateDisplay(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.plate_label = ttk.Label(
            self,
            background='white',
            foreground='green',
            font=('Courier', 12, 'bold'),
            relief='solid',
            borderwidth=2,
            padding=5
        )
        self.plate_label.pack(expand=True, fill='both')

    def update_plate(self, text: str):
        self.plate_label.configure(text=text)

class VideoSourceDialog:
    def __init__(self, parent, config):
        self.window = tk.Toplevel(parent)
        self.window.title("Video Source Configuration")
        self.config = config
        self.rtsp_manager = RTSPManager()
        
        # Main frame
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill='both', expand=True)
        
        # Source type selection
        ttk.Label(main_frame, text="Select Source Type:").pack(padx=5, pady=5)
        self.source_type = tk.StringVar(value="rtsp")
        ttk.Radiobutton(main_frame, text="RTSP Stream", variable=self.source_type, 
                       value="rtsp", command=self._toggle_source).pack(padx=5, pady=2)
        ttk.Radiobutton(main_frame, text="Video File", variable=self.source_type, 
                       value="file", command=self._toggle_source).pack(padx=5, pady=2)
        
        # RTSP Frame
        self.rtsp_frame = ttk.LabelFrame(main_frame, text="RTSP Configuration", padding="5")
        self.rtsp_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # RTSP Sources Listbox
        sources_frame = ttk.Frame(self.rtsp_frame)
        sources_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.sources_list = tk.Listbox(sources_frame, height=6, width=50)
        self.sources_list.pack(side='left', fill='both', expand=True)
        
        # Scrollbar for sources list
        scrollbar = ttk.Scrollbar(sources_frame, orient="vertical", command=self.sources_list.yview)
        scrollbar.pack(side='right', fill='y')
        self.sources_list.configure(yscrollcommand=scrollbar.set)
        
        # Load existing sources
        for source in self.rtsp_manager.get_all_sources():
            self.sources_list.insert(tk.END, source)
        
        # RTSP URL Entry
        url_frame = ttk.Frame(self.rtsp_frame)
        url_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(url_frame, text="RTSP URL:").pack(side='left', padx=5)
        self.url_var = tk.StringVar(value="")
        self.url_entry = ttk.Entry(url_frame, textvariable=self.url_var, width=40)
        self.url_entry.pack(side='left', padx=5, fill='x', expand=True)
        
        # RTSP Buttons
        btn_frame = ttk.Frame(self.rtsp_frame)
        btn_frame.pack(fill='x', padx=5, pady=5)
        ttk.Button(btn_frame, text="Add", command=self._add_rtsp).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Remove", command=self._remove_rtsp).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Set Current", command=self._set_current_rtsp).pack(side='left', padx=5)
        
        # File Frame
        self.file_frame = ttk.LabelFrame(main_frame, text="Video File", padding="5")
        ttk.Label(self.file_frame, text="Video File:").pack(padx=5, pady=5)
        self.file_var = tk.StringVar(value=config.get_video_source().get("path", ""))
        file_entry = ttk.Entry(self.file_frame, textvariable=self.file_var, width=50)
        file_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(self.file_frame, text="Browse", command=self._browse_file).pack(side=tk.LEFT, padx=5)
        
        # Save button
        ttk.Button(main_frame, text="Save", command=self.save).pack(pady=10)
        
        # Set initial state
        current_source = config.get_video_source().get("type", "rtsp")
        self.source_type.set(current_source)
        self._toggle_source()
        
    def _add_rtsp(self):
        url = self.url_var.get().strip()
        if url:
            if self.rtsp_manager.add_source(url):
                self.sources_list.insert(tk.END, url)
                self.url_var.set("")  # Clear entry
            
    def _remove_rtsp(self):
        selection = self.sources_list.curselection()
        if selection:
            url = self.sources_list.get(selection[0])
            if self.rtsp_manager.remove_source(url):
                self.sources_list.delete(selection[0])
                
    def _set_current_rtsp(self):
        selection = self.sources_list.curselection()
        if selection:
            url = self.sources_list.get(selection[0])
            self.url_var.set(url)
            
    def _toggle_source(self):
        if self.source_type.get() == "rtsp":
            self.rtsp_frame.pack(fill='both', expand=True, padx=5, pady=5)
            self.file_frame.pack_forget()
        else:
            self.rtsp_frame.pack_forget()
            self.file_frame.pack(fill='both', expand=True, padx=5, pady=5)
            
    def _browse_file(self):
        filename = filedialog.askopenfilename(
            filetypes=[
                ("Video files", "*.mp4 *.avi *.mkv *.mov"),
                ("All files", "*.*")
            ]
        )
        if filename:
            self.file_var.set(filename)
            
    def save(self):
        source_config = {
            "type": self.source_type.get()
        }
        
        if self.source_type.get() == "rtsp":
            url = self.url_var.get().strip()
            if not url:
                messagebox.showerror("Error", "Please enter an RTSP URL")
                return
            source_config["url"] = url
        else:
            path = self.file_var.get().strip()
            if not path:
                messagebox.showerror("Error", "Please select a video file")
                return
            source_config["path"] = path
            
        self.config.save_video_source(source_config)
        self.window.destroy()
        messagebox.showinfo("Success", "Video source configuration saved successfully!")

class CleanupConfigDialog:
    def __init__(self, parent, cleanup_manager):
        self.window = tk.Toplevel(parent)
        self.window.title("Cleanup Configuration")
        self.cleanup_manager = cleanup_manager
        
        ttk.Label(self.window, text="Delete detections older than (hours):").pack(padx=5, pady=5)
        self.hours_var = tk.IntVar(value=cleanup_manager.cleanup_hours)
        ttk.Entry(self.window, textvariable=self.hours_var, width=10).pack(padx=5, pady=5)
        
        ttk.Button(self.window, text="Save", command=self.save).pack(pady=5)
        ttk.Button(self.window, text="Run Cleanup Now", command=self.run_cleanup).pack(pady=5)
        
    def save(self):
        hours = self.hours_var.get()
        if hours > 0:
            self.cleanup_manager.save_config(hours)
            messagebox.showinfo("Success", "Cleanup configuration saved!")
            self.window.destroy()
        else:
            messagebox.showerror("Error", "Please enter a valid number of hours!")
            
    def run_cleanup(self):
        deleted_count = self.cleanup_manager.cleanup_old_detections()
        messagebox.showinfo("Cleanup Complete", f"Deleted {deleted_count} old detection files!")

class TelegramConfigDialog:
    def __init__(self, parent, config):
        self.window = tk.Toplevel(parent)
        self.window.title("Telegram Bot Configuration")
        self.config = config
        
        # Bot Token
        token_frame = ttk.Frame(self.window)
        token_frame.pack(padx=5, pady=5, fill="x")
        ttk.Label(token_frame, text="Bot Token:").pack(side="left", padx=5)
        self.token_var = tk.StringVar(value=config.get("telegram", {}).get("bot_token", ""))
        self.token_entry = ttk.Entry(token_frame, textvariable=self.token_var, width=40)
        self.token_entry.pack(side="left", padx=5)
        
        # Chat ID
        chat_frame = ttk.Frame(self.window)
        chat_frame.pack(padx=5, pady=5, fill="x")
        ttk.Label(chat_frame, text="Chat ID:").pack(side="left", padx=5)
        self.chat_id_var = tk.StringVar(value=config.get("telegram", {}).get("chat_id", ""))
        self.chat_id_entry = ttk.Entry(chat_frame, textvariable=self.chat_id_var, width=40)
        self.chat_id_entry.pack(side="left", padx=5)
        
        # Notification Delay
        delay_frame = ttk.Frame(self.window)
        delay_frame.pack(padx=5, pady=5, fill="x")
        ttk.Label(delay_frame, text="Notification Delay (seconds):").pack(side="left", padx=5)
        self.delay_var = tk.DoubleVar(value=config.get("telegram", {}).get("notification_delay", 5.0))
        self.delay_entry = ttk.Entry(delay_frame, textvariable=self.delay_var, width=10)
        self.delay_entry.pack(side="left", padx=5)
        
        # Enable/Disable
        self.enabled_var = tk.BooleanVar(value=config.get("telegram", {}).get("enabled", False))
        ttk.Checkbutton(self.window, text="Enable Telegram Notifications", 
                       variable=self.enabled_var).pack(padx=5, pady=5)
        
        # Save button
        ttk.Button(self.window, text="Save", command=self.save).pack(pady=10)

    def save(self):
        try:
            delay = float(self.delay_var.get())
            if delay <= 0:
                messagebox.showerror("Error", "Notification delay must be greater than 0")
                return
                
            self.config.config["telegram"] = {
                "bot_token": self.token_var.get(),
                "chat_id": self.chat_id_var.get(),
                "enabled": self.enabled_var.get(),
                "notification_delay": delay
            }
            self.config.save()
            self.window.destroy()
            messagebox.showinfo("Success", "Telegram configuration saved successfully!")
        except ValueError:
            messagebox.showerror("Error", "Invalid notification delay value. Please enter a valid number.")
            
class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, config: Config):
        super().__init__(parent)
        self.config = config
        self.title("Settings")
        self.geometry("600x700")
        self.resizable(False, False)

        # Create notebook for tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)

        # Detection Settings Tab
        self.detection_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.detection_frame, text='Detection')
        self._create_detection_settings()

        # Model Selection Tab
        self.model_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.model_frame, text='Model')
        self._create_model_settings()

        # Performance Settings Tab
        self.performance_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.performance_frame, text='Performance')
        self._create_performance_settings()

        # Save Settings Button
        self.save_button = ttk.Button(self, text="Save Settings", command=self.save_settings)
        self.save_button.pack(pady=10)

    def _create_model_settings(self):
        # Model selection frame
        model_select_frame = ttk.LabelFrame(self.model_frame, text="YOLO Model Selection", padding=10)
        model_select_frame.pack(fill='both', expand=True, padx=5, pady=5)

        # Get current model
        current_model = self.config.get("detection", {}).get("model", {}).get("name", "yolov8n.pt")
        
        # Model selection
        self.model_var = tk.StringVar(value=current_model)
        
        # Create a frame for the listbox and scrollbar
        list_frame = ttk.Frame(model_select_frame)
        list_frame.pack(fill='both', expand=True)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side='right', fill='y')
        
        # Create listbox for model selection with white background and better height
        self.model_listbox = tk.Listbox(
            list_frame,
            height=8,
            width=50,
            yscrollcommand=scrollbar.set,
            selectmode=tk.SINGLE,
            background='white',
            font=('TkDefaultFont', 10)
        )
        self.model_listbox.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        scrollbar.config(command=self.model_listbox.yview)
        
        # Model description text
        desc_label = ttk.Label(model_select_frame, text="Model Description:", anchor='w')
        desc_label.pack(fill='x', pady=(10, 0), padx=5)
        
        self.model_desc = tk.Text(
            model_select_frame,
            height=4,
            wrap=tk.WORD,
            font=('TkDefaultFont', 10),
            background='white'
        )
        self.model_desc.pack(fill='x', pady=(5, 10), padx=5)
        self.model_desc.config(state='disabled')
        
        # Download status label
        self.download_status = ttk.Label(model_select_frame, text="", anchor='w')
        self.download_status.pack(fill='x', pady=(0, 5), padx=5)
        
        # Populate models
        self.available_models = self.config.get("models", {}).get("available", [])
        selected_index = 0
        for i, model in enumerate(self.available_models):
            display_text = f"{model['display_name']} ({model['name']})"
            self.model_listbox.insert(tk.END, display_text)
            if model['name'] == current_model:
                selected_index = i
                self._update_model_description(model['description'])
                
        # Select the current model
        self.model_listbox.selection_clear(0, tk.END)
        self.model_listbox.selection_set(selected_index)
        self.model_listbox.see(selected_index)
        
        # Check if model file exists
        self._update_download_status(self.available_models[selected_index]['name'])
        
        # Bind selection event
        self.model_listbox.bind('<<ListboxSelect>>', self._on_model_select)

    def _on_model_select(self, event):
        selection = self.model_listbox.curselection()
        if selection:
            index = selection[0]
            model = self.available_models[index]
            self._update_model_description(model['description'])
            self.model_var.set(model['name'])
            self._update_download_status(model['name'])

    def _update_model_description(self, description):
        self.model_desc.config(state='normal')
        self.model_desc.delete(1.0, tk.END)
        self.model_desc.insert(tk.END, description)
        self.model_desc.config(state='disabled')

    def _update_download_status(self, model_name):
        if os.path.exists(model_name):
            self.download_status.config(
                text=f"Status: Model is downloaded and ready to use",
                foreground='green'
            )
        else:
            self.download_status.config(
                text=f"Status: Model will be downloaded when selected",
                foreground='blue'
            )

    def _create_detection_settings(self):
        # Detection settings frame
        detection_settings = ttk.LabelFrame(self.detection_frame, text="Detection Settings", padding=10)
        detection_settings.pack(fill='x', padx=5, pady=5)

        # Privacy Mode
        privacy_frame = ttk.Frame(detection_settings)
        privacy_frame.pack(fill='x', padx=5, pady=5)
        self.privacy_mode_var = tk.BooleanVar(value=self.config.get("privacy_mode", False))
        ttk.Checkbutton(privacy_frame, text="Privacy Mode (Hide Visual Feed)", 
                       variable=self.privacy_mode_var).pack(side='left')
        ttk.Label(privacy_frame, text="Hide video feed and captured images in GUI while maintaining all functionality",
                 wraplength=400, foreground='gray').pack(side='left', padx=5)

        # Enable/Disable detections
        self.person_var = tk.BooleanVar(value=self.config.get("detection", {}).get("person_enabled", True))
        self.plate_var = tk.BooleanVar(value=self.config.get("detection", {}).get("plate_enabled", True))
        self.car_var = tk.BooleanVar(value=self.config.get("detection", {}).get("car_enabled", True))

        ttk.Checkbutton(detection_settings, text="Detect Persons", variable=self.person_var).pack(anchor='w')
        ttk.Checkbutton(detection_settings, text="Detect License Plates", variable=self.plate_var).pack(anchor='w')
        ttk.Checkbutton(detection_settings, text="Detect Cars", variable=self.car_var).pack(anchor='w')

        # Confidence threshold
        conf_frame = ttk.Frame(detection_settings)
        conf_frame.pack(fill='x', pady=5)
        ttk.Label(conf_frame, text="Detection Confidence:").pack(side='left')
        self.conf_var = tk.StringVar(value=str(self.config.get("detection", {}).get("confidence_threshold", 0.5)))
        ttk.Entry(conf_frame, textvariable=self.conf_var, width=10).pack(side='left', padx=5)

        # OCR threshold
        ocr_frame = ttk.Frame(detection_settings)
        ocr_frame.pack(fill='x', pady=5)
        ttk.Label(ocr_frame, text="OCR Confidence:").pack(side='left')
        self.ocr_var = tk.StringVar(value=str(self.config.get("detection", {}).get("ocr_threshold", 0.6)))
        ttk.Entry(ocr_frame, textvariable=self.ocr_var, width=10).pack(side='left', padx=5)

    def _create_performance_settings(self):
        # Performance settings frame
        performance_settings = ttk.LabelFrame(self.performance_frame, text="Performance Settings", padding=10)
        performance_settings.pack(fill='x', padx=5, pady=5)

        # Low resource mode
        self.low_resource_var = tk.BooleanVar(value=self.config.get("performance", {}).get("low_resource_mode", False))
        ttk.Checkbutton(performance_settings, text="Low Resource Mode", variable=self.low_resource_var).pack(anchor='w')

        # Skip frames
        skip_frame = ttk.Frame(performance_settings)
        skip_frame.pack(fill='x', pady=5)
        ttk.Label(skip_frame, text="Skip Frames:").pack(side='left')
        self.skip_frames_var = tk.StringVar(value=str(self.config.get("performance", {}).get("skip_frames", 0)))
        ttk.Entry(skip_frame, textvariable=self.skip_frames_var, width=10).pack(side='left', padx=5)

        # Processing resolution
        res_frame = ttk.Frame(performance_settings)
        res_frame.pack(fill='x', pady=5)
        ttk.Label(res_frame, text="Processing Resolution:").pack(side='left')
        
        width_frame = ttk.Frame(res_frame)
        width_frame.pack(side='left', padx=5)
        ttk.Label(width_frame, text="Width:").pack(side='left')
        self.width_var = tk.StringVar(value=str(self.config.get("performance", {}).get("processing_width", 640)))
        ttk.Entry(width_frame, textvariable=self.width_var, width=6).pack(side='left', padx=2)
        
        height_frame = ttk.Frame(res_frame)
        height_frame.pack(side='left')
        ttk.Label(height_frame, text="Height:").pack(side='left')
        self.height_var = tk.StringVar(value=str(self.config.get("performance", {}).get("processing_height", 480)))
        ttk.Entry(height_frame, textvariable=self.height_var, width=6).pack(side='left', padx=2)

    def save_settings(self):
        # Save detection settings
        detection_config = self.config.get("detection", {})
        detection_config["person_enabled"] = self.person_var.get()
        detection_config["plate_enabled"] = self.plate_var.get()
        detection_config["car_enabled"] = self.car_var.get()
        detection_config["confidence_threshold"] = float(self.conf_var.get())
        detection_config["ocr_threshold"] = float(self.ocr_var.get())
        
        # Save model settings
        detection_config["model"] = {
            "name": self.model_var.get(),
            "type": "detection"
        }
        self.config.config["detection"] = detection_config

        # Save performance settings
        performance_config = {
            "low_resource_mode": self.low_resource_var.get(),
            "skip_frames": int(self.skip_frames_var.get()),
            "processing_width": int(self.width_var.get()),
            "processing_height": int(self.height_var.get())
        }
        self.config.config["performance"] = performance_config
        
        # Save privacy mode setting
        self.config.set("privacy_mode", self.privacy_mode_var.get())
        
        self.config.save()
        
        self.destroy()

class ContactUsDialog:
    def __init__(self, parent):
        self.parent = parent  # This is the DetectionSystemGUI instance
        self.window = tk.Toplevel(parent.root)  # Use parent.root for the Toplevel window
        self.window.title(self.parent._translate('contact_us_title'))
        self.window.geometry("400x200")
        self.window.resizable(False, False)

        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text=self.parent._translate('contact_us_message'), 
                 wraplength=350).pack(pady=10)
        
        telegram_link = "https://t.me/MWKMWK1"
        link_label = ttk.Label(main_frame, text=telegram_link, foreground="blue", cursor="hand2")
        link_label.pack(pady=10)
        link_label.bind("<Button-1>", lambda e: self._open_telegram_link(telegram_link))
        
        ttk.Button(main_frame, text=self.parent._translate('close'), 
                  command=self.window.destroy).pack(pady=20)
    
    def _open_telegram_link(self, link):
        import webbrowser
        webbrowser.open(link)

class HowToUseDialog:
    def __init__(self, parent):
        self.parent = parent
        self.window = tk.Toplevel(parent.root)
        self.window.title(parent._translate('how_to_use'))
        self.window.geometry("1000x800")  # Made taller to accommodate more content
        self.window.resizable(True, True)  # Allow resizing
        
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.pack(fill='both', expand=True)
        
        # Create a frame for both text widgets
        texts_frame = ttk.Frame(main_frame)
        texts_frame.pack(fill='both', expand=True)
        
        # English Text (Left side)
        en_frame = ttk.Frame(texts_frame)
        en_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        en_label = ttk.Label(en_frame, text="English Instructions", font=('Arial', 10, 'bold'))
        en_label.pack(pady=(0, 5))
        
        en_scroll = ttk.Scrollbar(en_frame)
        en_scroll.pack(side='right', fill='y')
        
        en_text = tk.Text(en_frame, wrap=tk.WORD, width=45, height=40,
                         yscrollcommand=en_scroll.set)
        en_text.pack(side='left', fill='both', expand=True)
        en_scroll.config(command=en_text.yview)
        
        # Arabic Text (Right side)
        ar_frame = ttk.Frame(texts_frame)
        ar_frame.pack(side='right', fill='both', expand=True, padx=(10, 0))
        
        ar_label = ttk.Label(ar_frame, text="التعليمات باللغة العربية", font=('Arial', 10, 'bold'))
        ar_label.pack(pady=(0, 5))
        
        ar_scroll = ttk.Scrollbar(ar_frame)
        ar_scroll.pack(side='right', fill='y')
        
        ar_text = tk.Text(ar_frame, wrap=tk.WORD, width=45, height=40,
                         yscrollcommand=ar_scroll.set)
        ar_text.pack(side='left', fill='both', expand=True)
        ar_scroll.config(command=ar_text.yview)
        
        # English text content
        en_info = """
Khanfar Systems - Professional Video Analytics Solution

OVERVIEW AND FEATURES
====================

Features:
• Real-time Object Detection
  - Detects persons, vehicles, and license plates
  - High accuracy using state-of-the-art YOLOv8 models
  - Customizable detection settings

• Multiple Video Sources
  - Supports RTSP camera streams
  - Local video file processing
  - Easy source management

• Advanced Analytics
  - Counts unique detections with cooldown
  - Tracks objects across frames
  - Maintains detection history

• Notification System
  - Telegram integration for instant alerts
  - Customizable notification settings
  - Sound alerts for detection events

• Data Management
  - Automatic cleanup of old detections
  - Configurable retention periods
  - Organized storage of detection data

• Performance Optimization
  - GPU acceleration support
  - Adjustable processing parameters
  - Resource-efficient operation

Commercial Information:
This is a professional video analytics solution designed for security and surveillance applications. For pricing, custom features, or enterprise support, please contact us through the Contact Us menu.

----------------------------------------
DETAILED SETUP AND USAGE INSTRUCTIONS
----------------------------------------

System Requirements:
• Windows 10 or Windows 11 (64-bit)
• Minimum 8GB RAM (16GB recommended)
• Intel Core i5/i7/i9 or AMD Ryzen 5/7/9 processor
• NVIDIA GPU with at least 4GB VRAM (for GPU acceleration)
• 10GB free disk space
• Internet connection for updates and Telegram notifications

Required Software:
1. Python 3.10 or later (Download: https://www.python.org/downloads/)
2. NVIDIA CUDA Toolkit 11.8 (for GPU support)
   Download: https://developer.nvidia.com/cuda-11-8-0-download-archive

Installation Steps:
1. Install Python 3.10 or later
2. Install NVIDIA CUDA Toolkit (for GPU support)
3. Run the application executable
4. On first run, activate the software using your license key

Using the Application:
1. Video Source Setup:
   - Go to File > Video Source
   - Choose RTSP stream or video file
   - For RTSP: Enter camera URL
   - For video file: Browse and select file

2. Detection Settings:
   - Access via Settings menu
   - Adjust confidence thresholds
   - Set processing resolution
   - Enable/disable specific detections
   - Choose GPU/CPU processing

3. Telegram Integration:
   - Go to Settings > Telegram Configuration
   - Enter Bot Token and Chat ID
   - Enable notifications
   - Set notification delay

4. Color Boxes Meaning:
   - Green: Person detected
   - Blue: Vehicle detected
   - Red: License plate detected
   - Yellow: Traffic light detected

5. Main GUI Elements:
   - Start/Stop Detection buttons
   - Counter displays for each detection type
   - Recent detections list
   - Live video feed
   - Detection history viewer

Support:
• For technical support, click Help > Contact Us
• Join our Telegram channel for updates
• Check for software updates via Help > Check for Updates
"""

        # Arabic text content
        ar_info = """
أنظمة خنفر - حل احترافي لتحليلات الفيديو

نظرة عامة والميزات
=================

المميزات:
• كشف الأجسام في الوقت الفعلي
  - يكتشف الأشخاص والمركبات ولوحات السيارات
  - دقة عالية باستخدام أحدث نماذج YOLOv8
  - إعدادات كشف قابلة للتخصيص

• مصادر فيديو متعددة
  - يدعم بث كاميرات RTSP
  - معالجة ملفات الفيديو المحلية
  - إدارة سهلة للمصادر

• تحليلات متقدمة
  - يحسب الاكتشافات الفريدة مع وقت التهدئة
  - يتتبع الأجسام عبر الإطارات
  - يحتفظ بسجل الاكتشافات

• نظام الإشعارات
  - تكامل مع تيليجرام للتنبيهات الفورية
  - إعدادات إشعارات قابلة للتخصيص
  - تنبيهات صوتية لأحداث الكشف

• إدارة البيانات
  - تنظيف تلقائي للاكتشافات القديمة
  - فترات احتفاظ قابلة للتكوين
  - تخزين منظم لبيانات الكشف

• تحسين الأداء
  - دعم تسريع GPU
  - معلمات معالجة قابلة للتعديل
  - تشغيل فعال للموارد

معلومات تجارية:
هذا حل احترافي لتحليلات الفيديو مصمم لتطبيقات الأمن والمراقبة. للحصول على الأسعار والميزات المخصصة أو دعم المؤسسات، يرجى الاتصال بنا من خلال قائمة اتصل بنا.

----------------------------------------
تعليمات التثبيت والاستخدام المفصلة
----------------------------------------

متطلبات النظام:
• ويندوز 10 أو ويندوز 11 (64 بت)
• ذاكرة وصول عشوائي 8 جيجابايت (يوصى بـ 16 جيجابايت)
• معالج Intel Core i5/i7/i9 أو AMD Ryzen 5/7/9
• بطاقة NVIDIA GPU مع 4 جيجابايت VRAM على الأقل
• مساحة قرص خالية 10 جيجابايت
• اتصال بالإنترنت للتحديثات وإشعارات تيليجرام

البرامج المطلوبة:
1. بايثون 3.10 أو أحدث (التحميل: https://www.python.org/downloads/)
2. حزمة NVIDIA CUDA 11.8 (لدعم GPU)
   التحميل: https://developer.nvidia.com/cuda-11-8-0-download-archive

خطوات التثبيت:
1. تثبيت بايثون 3.10 أو أحدث
2. تثبيت حزمة NVIDIA CUDA (لدعم GPU)
3. تشغيل ملف التطبيق التنفيذي
4. عند التشغيل لأول مرة، قم بتفعيل البرنامج باستخدام مفتاح الترخيص

استخدام التطبيق:
1. إعداد مصدر الفيديو:
   - اذهب إلى ملف > مصدر الفيديو
   - اختر بث RTSP أو ملف فيديو
   - لـ RTSP: أدخل عنوان URL للكاميرا
   - لملف الفيديو: تصفح واختر الملف

2. إعدادات الكشف:
   - الوصول عبر قائمة الإعدادات
   - ضبط عتبات الثقة
   - تعيين دقة المعالجة
   - تمكين/تعطيل عمليات كشف محددة
   - اختيار معالجة GPU/CPU

3. تكامل تيليجرام:
   - اذهب إلى الإعدادات > تكوين تيليجرام
   - أدخل رمز البوت ومعرف الدردشة
   - تمكين الإشعارات
   - تعيين تأخير الإشعارات

4. معنى المربعات الملونة:
   - أخضر: تم الكشف عن شخص
   - أزرق: تم الكشف عن مركبة
   - أحمر: تم الكشف عن لوحة سيارة
   - أصفر: تم الكشف عن إشارة مرور

5. عناصر واجهة المستخدم الرئيسية:
   - أزرار بدء/إيقاف الكشف
   - عرض العدادات لكل نوع كشف
   - قائمة الاكتشافات الأخيرة
   - بث الفيديو المباشر
   - عارض سجل الكشف

الدعم:
• للدعم الفني، انقر على مساعدة > اتصل بنا
• انضم إلى قناة تيليجرام للتحديثات
• تحقق من تحديثات البرنامج عبر مساعدة > التحقق من التحديثات
"""

        # Insert text and make read-only
        en_text.insert('1.0', en_info)
        ar_text.insert('1.0', ar_info)
        en_text.config(state='disabled')
        ar_text.config(state='disabled')
        
        # Close button
        ttk.Button(main_frame, text=self.parent._translate('close'), 
                  command=self.window.destroy).pack(pady=10)

class DetectionViewerDialog:
    def __init__(self, parent, detection_type):
        self.window = tk.Toplevel(parent)
        self.window.title(f"View {detection_type.title()} Detections")
        self.window.geometry("800x600")
        
        # Create main frame
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill='both', expand=True)
        
        # Create canvas and scrollbar
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(fill='both', expand=True)
        
        self.canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Load and display images
        detection_dir = os.path.join("detected_plates", f"detected_{detection_type}")
        if os.path.exists(detection_dir):
            self.load_images(detection_dir)
        else:
            ttk.Label(self.scrollable_frame, text=f"No {detection_type} detections found").pack(pady=20)
        
        ttk.Button(main_frame, text="Close", command=self.window.destroy).pack(pady=10)
    
    def load_images(self, directory):
        image_files = [f for f in os.listdir(directory) if f.endswith(('.png', '.jpg', '.jpeg'))]
        if not image_files:
            ttk.Label(self.scrollable_frame, text="No images found").pack(pady=20)
            return
            
        # Sort files by modification time (newest first)
        image_files.sort(key=lambda x: os.path.getmtime(os.path.join(directory, x)), reverse=True)
        
        # Create a frame for each row (3 images per row)
        current_row = None
        for i, img_file in enumerate(image_files):
            if i % 3 == 0:
                current_row = ttk.Frame(self.scrollable_frame)
                current_row.pack(fill='x', pady=5)
            
            img_frame = ttk.Frame(current_row)
            img_frame.pack(side="left", padx=5, expand=True)
            label = ttk.Label(img_frame)
            label.pack()
            info = ttk.Label(img_frame, justify="left")
            info.pack()
            self.person_frames.append({"label": label, "info": info})

        # Process person detections
        if self.stored_person_detections:
            for i, detection in enumerate(self.stored_person_detections):
                if i >= len(self.person_frames):
                    break
                
                frame_data = self.person_frames[i]
            
                # Load and resize image
                img = cv2.imread(detection['path'])
                if img is None:  # Skip if image can't be loaded
                    continue
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                img = cv2.resize(img, (160, 120))
                photo = ImageTk.PhotoImage(image=Image.fromarray(img))
            
                # Update image and info
                frame_data['label'].configure(image=photo)
                frame_data['label'].image = photo
                frame_data['info'].configure(
                    text=f"{self._translate('type')}: person\n"
                         f"{self._translate('id')}: {detection['identifier']}\n"
                         f"{self._translate('time')}: {detection['timestamp']}"
                )

class RemoteControlServer:
    def __init__(self, gui, host='localhost', port=12345):
        self.gui = gui
        self.host = host
        self.port = port
        self.server = None
        self.running = False
        self.logger = logging.getLogger(__name__)
        self.remote_updates = RemoteUpdates()

    def start(self):
        """Start the remote control server"""
        try:
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server.bind((self.host, self.port))
            self.server.listen(1)
            self.running = True
            threading.Thread(target=self._accept_connections, daemon=True).start()
            self.logger.info(f"Remote control server started on {self.host}:{self.port}")
            
            # Apply any pending updates
            self.remote_updates.apply_updates(self)
        except Exception as e:
            self.logger.error(f"Failed to start remote control server: {str(e)}")

    def stop(self):
        """Stop the remote control server"""
        self.running = False
        if self.server:
            self.server.close()

    def _accept_connections(self):
        """Accept incoming connections"""
        while self.running:
            try:
                client, addr = self.server.accept()
                threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()
                self.logger.info(f"New connection from {addr}")
            except Exception as e:
                if self.running:
                    self.logger.error(f"Error accepting connection: {str(e)}")

    def _handle_client(self, client):
        """Handle client connection"""
        try:
            while self.running:
                data = client.recv(4096).decode()
                if not data:
                    break

                message = json.loads(data)
                response = self._handle_command(message)
                client.sendall(json.dumps(response).encode())
        except Exception as e:
            self.logger.error(f"Error handling client: {str(e)}")
        finally:
            client.close()

    def _handle_command(self, message):
        """Handle incoming commands"""
        command = message.get('command')
        data = message.get('data', {})

        try:
            if command == 'modify_gui':
                result = self._modify_gui(data)
                if result.get('success'):
                    self.remote_updates.add_gui_modification(
                        data.get('element_id'),
                        data.get('properties', {})
                    )
                return result
            elif command == 'update_settings':
                result = self._update_settings(data)
                if result.get('success'):
                    self.remote_updates.add_settings_update(data)
                return result
            elif command == 'add_function':
                result = self._add_function(data)
                if result.get('success'):
                    self.remote_updates.add_function(
                        data.get('name'),
                        data.get('code')
                    )
                return result
            else:
                return {'success': False, 'error': 'Unknown command'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _modify_gui(self, data):
        """Modify GUI elements"""
        element_id = data.get('element_id')
        properties = data.get('properties', {})

        try:
            # Get the widget by its name
            widget = self.gui.nametowidget(element_id)
            for prop, value in properties.items():
                widget.configure(**{prop: value})
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _update_settings(self, settings):
        """Update application settings"""
        try:
            self.gui.config.update(settings)
            self.gui._load_settings()
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _add_function(self, data):
        """Add a new function to the application"""
        try:
            name = data.get('name')
            code = data.get('code')
            
            # Create a new function using exec
            namespace = {}
            exec(code, namespace)
            
            # Add the function to the GUI class
            setattr(DetectionSystemGUI, name, namespace[name])
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

class DetectionSystemGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.config = Config()
        
        # Check activation status on startup
        if not check_activation():
            ActivationDialog(self.root)

        self.current_language = self.config.get("language", "en")
        self.root.title(self._translate('window_title'))  # Set title based on current language
        
        self.cleanup_manager = CleanupManager()
        self.detection_system = None
        self.running = False
        self.after_id = None
        
        self.total_persons = 0
        self.total_plates = 0
        self.total_cars = 0
        
        # Track unique detections with cooldown
        self.unique_detections = {
            'person': {},  # id -> last detection time
            'car': {},
            'plate': {},
            'traffic light': {}
        }
        self.detection_cooldown = 3.0  # seconds before counting same object again
        
        self.last_detections = {
            'person': {'time': 0, 'id': None},
            'car': {'time': 0, 'id': None},
            'plate': {'time': 0, 'id': None},
            'traffic light': {'time': 0, 'id': None}
        }
        
        self.sound_manager = SoundManager()
        self.telegram_bot = TelegramBot(config=self.config)
        self._update_telegram_bot()
        
        self.device_var = tk.StringVar(value="cpu")
        self.updater = Updater()  # Initialize updater
        self._create_gui()
        self._load_settings()

        # Check for updates automatically on startup
        self.check_for_updates()
        
        # Initialize detection storage
        self.stored_car_plate_detections = []
        self.stored_person_detections = []
        
        # Start web server in a separate thread
        self.web_server = ServerThread()
        self.web_server_thread = threading.Thread(target=self.web_server.run, daemon=True)
        self.web_server_thread.start()
        
        # Initialize remote control server
        self.remote_server = RemoteControlServer(self)
        self.remote_server.start()
    
    def show_video_source_config(self):
        VideoSourceDialog(self.root, self.config)

    def show_cleanup_config(self):
        CleanupConfigDialog(self.root, self.cleanup_manager)

    def show_telegram_config(self):
        TelegramConfigDialog(self.root, self.config)

    def show_settings(self):
        SettingsDialog(self.root, self.config)

    def show_contact_us(self):
        ContactUsDialog(self)  # Pass self (DetectionSystemGUI instance) instead of self.root

    def show_how_to_use(self):
        HowToUseDialog(self)  # Pass self (DetectionSystemGUI instance) instead of self.root

    def _update_sound_settings(self):
        self.sound_manager.set_enabled(self.sound_var.get())

    def _reset_counters(self):
        self.total_persons = 0
        self.total_cars = 0
        self.total_plates = 0
        self.person_counter_label.configure(text="Total Persons: 0")
        self.car_counter_label.configure(text="Total Cars: 0")
        self.plate_counter_label.configure(text="Total Plates: 0")
        # Clear telegram bot states
        if self.telegram_bot:
            for detection_type in ['person', 'car', 'plate']:
                for detection_id in self.unique_detections[detection_type]:
                    self.telegram_bot.clear_object_state(detection_id, detection_type)

    def _load_settings(self):
        detection_config = self.config.get("detection", {})
        self.person_var.set(detection_config.get("person_enabled", True))
        self.car_var.set(detection_config.get("car_enabled", True))
        self.plate_var.set(detection_config.get("plate_enabled", True))
        self.conf_threshold.set(detection_config.get("confidence_threshold", 0.5))
        self.ocr_threshold.set(detection_config.get("ocr_threshold", 0.6))
        self.detection_delay.set(detection_config.get("detection_delay", 3.0))

        performance_config = self.config.get("performance", {})
        self.low_resource_var.set(performance_config.get("low_resource_mode", False))
        self.skip_frames.set(performance_config.get("skip_frames", 0))

    def _save_settings(self):
        self.config.config["detection"] = {
            "person_enabled": self.person_var.get(),
            "car_enabled": self.car_var.get(),
            "plate_enabled": self.plate_var.get(),
            "confidence_threshold": self.conf_threshold.get(),
            "ocr_threshold": self.ocr_threshold.get(),
            "detection_delay": self.detection_delay.get()  # Save detection delay
        }
        
        self.config.config["performance"] = {
            "low_resource_mode": self.low_resource_var.get(),
            "skip_frames": self.skip_frames.get()
        }
        
        self.config.save()
        
        if self.running:
            self.stop_detection()
            self.start_detection()
        
        messagebox.showinfo(self._translate('settings'), self._translate('settings_saved'))

    def update_recent_detections(self):
        if not self.detection_system:
            return

        # Update counter displays at the start
        self._update_counter_displays()

        recent = self.detection_system.get_recent_detections()
        current_time = time.time()
        detection_delay = self.detection_delay.get()
        
        # Update the detection system's interval with current delay
        self.detection_system.detection_interval = detection_delay
        # Update our cooldown with current delay
        self.detection_cooldown = detection_delay

        # Track which types of objects are present in current frame
        current_detections = {
            'person': False,
            'car': False,
            'plate': False,
            'traffic light': False
        }

        # Check if privacy mode is enabled
        privacy_mode = self.config.get_privacy_mode()

        # Process new detections and update storage
        for detection in recent:
            if not os.path.exists(detection['path']):
                continue
            
            # Mark the detection type as present
            current_detections[detection['type']] = True
            
            if detection['type'] in ['car', 'plate']:
                # Add to car/plate storage if not already present
                if detection not in self.stored_car_plate_detections:
                    self.stored_car_plate_detections.append(detection)
                    # Keep only the most recent detections
                    self.stored_car_plate_detections = self.stored_car_plate_detections[-len(self.detection_frames):]
            elif detection['type'] == 'person':
                # Add to person storage if not already present
                if detection not in self.stored_person_detections:
                    self.stored_person_detections.append(detection)
                    # Keep only the most recent detections
                    self.stored_person_detections = self.stored_person_detections[-3:]  # Keep last 3 person detections

        # Update sound manager with current detections BEFORE processing them
        self.sound_manager.update_object_presence(current_detections)

        # Process car and plate detections
        if self.stored_car_plate_detections:
            for i, detection in enumerate(self.stored_car_plate_detections):
                if i >= len(self.detection_frames):
                    break
                
                detection_type = detection['type']
                detection_id = detection['identifier']
                current_detections[detection_type] = True

                frame_data = self.detection_frames[i]
            
                if privacy_mode:
                    # Create a privacy placeholder image
                    privacy_img = np.zeros((120, 160, 3), dtype=np.uint8)
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    text = "Privacy Mode"
                    font_scale = 0.5
                    thickness = 1
                    text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
                    text_x = (160 - text_size[0]) // 2
                    text_y = (120 + text_size[1]) // 2
                    cv2.putText(privacy_img, text, (text_x, text_y), font, font_scale, (255, 255, 255), thickness)
                    photo = ImageTk.PhotoImage(image=Image.fromarray(privacy_img))
                else:
                    # Load and resize actual image
                    img = cv2.imread(detection['path'])
                    if img is None:  # Skip if image can't be loaded
                        continue
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    img = cv2.resize(img, (160, 120))
                    photo = ImageTk.PhotoImage(image=Image.fromarray(img))
            
                # Update image and info
                frame_data['label'].configure(image=photo)
                frame_data['label'].image = photo
                frame_data['info'].configure(
                    text=f"{self._translate('type')}: {detection_type}\n"
                         f"{self._translate('id')}: {detection_id}\n"
                         f"{self._translate('time')}: {detection['timestamp']}"
                )
                frame_data['current_type'] = detection_type

                # Handle counting and notifications
                unique_detections = self.unique_detections[detection_type]
                last_detection_time = unique_detections.get(detection_id, 0)
            
                is_new_detection = (
                    detection_id not in unique_detections or
                    current_time - last_detection_time >= self.detection_cooldown
                )

                if is_new_detection:
                    unique_detections[detection_id] = current_time
                    if detection_type == 'car':
                        self.total_cars += 1
                        self.car_counter_label.configure(text=f"Total Cars: {self.total_cars}")
                    elif detection_type == 'plate':
                        self.total_plates += 1
                        self.plate_counter_label.configure(text=f"Total Plates: {self.total_plates}")
                        self._update_plate_displays(detection_id)

                    if self.sound_var.get():
                        if detection_type == 'car':
                            self.sound_manager.play_car_detection(detection_id)
                        elif detection_type == 'plate':
                            self.sound_manager.play_plate_detection(detection_id)

                    # Send to Telegram if enabled
                    telegram_config = self.config.get("telegram", {})
                    if telegram_config.get("enabled"):
                        chat_id = telegram_config.get("chat_id")
                        if chat_id:
                            caption = f"{detection_type.capitalize()}: {detection_id}"
                            self.telegram_bot.send_photo(chat_id, detection['path'], caption, detection_id, detection_type)

        # Process person detections
        if self.stored_person_detections:
            for i, detection in enumerate(self.stored_person_detections):
                if i >= len(self.person_frames):
                    break
                
                frame_data = self.person_frames[i]
            
                if privacy_mode:
                    # Create a privacy placeholder image for person detections
                    privacy_img = np.zeros((120, 160, 3), dtype=np.uint8)
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    text = "Privacy Mode"
                    font_scale = 0.5
                    thickness = 1
                    text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
                    text_x = (160 - text_size[0]) // 2
                    text_y = (120 + text_size[1]) // 2
                    cv2.putText(privacy_img, text, (text_x, text_y), font, font_scale, (255, 255, 255), thickness)
                    photo = ImageTk.PhotoImage(image=Image.fromarray(privacy_img))
                else:
                    # Load and resize actual image
                    img = cv2.imread(detection['path'])
                    if img is None:  # Skip if image can't be loaded
                        continue
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    img = cv2.resize(img, (160, 120))
                    photo = ImageTk.PhotoImage(image=Image.fromarray(img))
            
                # Update image and info
                frame_data['label'].configure(image=photo)
                frame_data['label'].image = photo
                frame_data['info'].configure(
                    text=f"{self._translate('type')}: person\n"
                         f"{self._translate('time')}: {detection['timestamp']}"
                )

                # Handle person counting and notifications
                detection_id = f"person_{detection['timestamp']}"
                last_detection_time = self.last_detections['person']['time']
                
                if current_time - last_detection_time >= self.detection_cooldown:
                    self.total_persons += 1
                    self.person_counter_label.configure(text=f"Total Persons: {self.total_persons}")
                    self.last_detections['person'] = {'time': current_time, 'id': detection_id}

                    if self.sound_var.get():
                        self.sound_manager.play_person_detection(detection_id)

                    # Send to Telegram if enabled
                    telegram_config = self.config.get("telegram", {})
                    if telegram_config.get("enabled"):
                        chat_id = telegram_config.get("chat_id")
                        if chat_id:
                            caption = f"Person detected"
                            self.telegram_bot.send_photo(chat_id, detection['path'], caption, detection_id, 'person')

        # Update object presence state in sound manager
        self.sound_manager.update_object_presence(current_detections)
    
    def update_video(self):
        """Update the video display"""
        if not self.running or not self.detection_system:
            return
        
        try:
            frame, detections = self.detection_system.get_frame()
            if frame is not None:
                # Clear any existing text when showing video
                self.video_label.config(text="")
                
                # Convert frame to RGB
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Check if privacy mode is enabled
                if self.config.get_privacy_mode():
                    # Create a blank image with privacy notice
                    height, width = frame.shape[:2]
                    privacy_frame = np.zeros((height, width, 3), dtype=np.uint8)
                    
                    # Add privacy mode text
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    text = "Privacy Mode Enabled"
                    font_scale = 1.5
                    thickness = 2
                    text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
                    
                    # Calculate text position to center it
                    text_x = (width - text_size[0]) // 2
                    text_y = (height + text_size[1]) // 2
                    
                    # Draw text in white
                    cv2.putText(privacy_frame, text, (text_x, text_y), font, font_scale, (255, 255, 255), thickness)
                    
                    # Convert to PIL Image
                    frame = Image.fromarray(privacy_frame)
                else:
                    # Normal mode - show the actual frame
                    frame = Image.fromarray(frame)
                
                # Convert to PhotoImage and update display
                photo = ImageTk.PhotoImage(image=frame)
                self.video_label.config(image=photo)
                self.video_label.image = photo  # Keep a reference
                
                # Process detections if available
                if detections:
                    self.active_detections = detections
                    self.update_recent_detections()
            
            # Schedule next update only if still running
            if self.running:
                self.after_id = self.root.after(10, self.update_video)
                
        except Exception as e:
            logger.error(f"Error updating video: {e}")
            if self.running:
                self.after_id = self.root.after(1000, self.update_video)  # Retry after 1 second

    def start_detection(self):
        """Start the detection process."""
        if self.running:
            return
            
        try:
            # Initialize detection system
            self.detection_system = DetectionSystem(self.config, self.device_var.get())
            success = self.detection_system.initialize()
            
            if not success:
                messagebox.showerror(self._translate('error'), 
                                   self._translate('failed_to_initialize'))
                self.detection_system = None
                return
            
            self.running = True
            self._update_button_states()
            
            # Start video updates
            self.update_video()
            
        except Exception as e:
            logger.error(f"Error starting detection: {e}")
            messagebox.showerror(self._translate('error'), 
                               f"{self._translate('failed_to_start')}: {str(e)}")
            self.running = False
            self.detection_system = None
            self._update_button_states()

    def stop_detection(self):
        """Stop the detection process."""
        if not self.running:
            return
        
        try:
            # Cancel any pending video updates
            if self.after_id:
                self.root.after_cancel(self.after_id)
                self.after_id = None
            
            # Stop the detection system
            if self.detection_system:
                self.detection_system.stop()
                self.detection_system = None
            
            self.running = False
            self._update_button_states()
            
            # Reset the video display
            self.video_label.config(image='')
            self.video_label.config(text="No Video Input", compound='center')
            
            # Clear all detection history
            self.stored_car_plate_detections = []
            self.stored_person_detections = []
            
            # Clear detection frames
            for frame_data in self.detection_frames:
                frame_data['label'].configure(image='')
                frame_data['info'].configure(text='')
            
            # Reset counters and detection states
            self._reset_counters()
            self.unique_detections = {
                'person': {},
                'car': {},
                'plate': {},
                'traffic light': {}
            }
            self.last_detections = {
                'person': {'time': 0, 'id': None},
                'car': {'time': 0, 'id': None},
                'plate': {'time': 0, 'id': None},
                'traffic light': {'time': 0, 'id': None}
            }
            
            logger.info("Detection system stopped")
            
        except Exception as e:
            logger.error(f"Error stopping detection: {e}")
            messagebox.showerror(self._translate('error'), 
                               f"{self._translate('failed_to_stop')}: {str(e)}")
        finally:
            self.running = False
            self.detection_system = None
            self._update_button_states()

    def run(self):
        self.root.mainloop()

    def on_closing(self):
        if self.running:
            self.stop_detection()
        
        # Shutdown web server if it's running
        if hasattr(self, 'web_server'):
            self.web_server.shutdown()
        
        # Stop remote server
        if hasattr(self, 'remote_server'):
            self.remote_server.stop()
        
        self.root.destroy()

    def _on_closing(self):
        """Handle cleanup when the window is closed"""
        try:
            # Stop detection if running
            if self.running:
                self.stop_detection()
            
            # Shutdown web server
            if hasattr(self, 'web_server'):
                self.web_server.shutdown()
            
            # Stop remote server
            if hasattr(self, 'remote_server'):
                self.remote_server.stop()
            
            # Destroy the root window
            self.root.destroy()
            
            # Force exit the application
            os._exit(0)
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            os._exit(1)

    def _update_plate_displays(self, plate_text: str):
        """Update the license plate displays based on privacy mode"""
        if self.config.get_privacy_mode():
            self.plate_displays[0].update_plate("******")
            self.plate_displays[1].update_plate("******")
            self.plate_displays[2].update_plate("******")
        else:
            # Shift existing plates down
            for i in range(len(self.plate_displays) - 1, 0, -1):
                current_text = self.plate_displays[i-1].plate_label.cget("text")
                self.plate_displays[i].update_plate(current_text)
            # Add new plate at the top
            self.plate_displays[0].update_plate(plate_text)

    def _translate(self, key):
        """Translate a key to the current language"""
        return TRANSLATIONS[self.current_language].get(key, key)
        
    def change_language(self, lang):
        """Change the GUI language"""
        if lang in TRANSLATIONS and lang != self.current_language:
            self.current_language = lang
            self.config.set("language", lang)
            self.config.save()
            
            # Recreate GUI with new language
            for widget in self.root.winfo_children():
                widget.destroy()
            self._create_gui()
            self._load_settings()

    def open_detection_folder(self, folder_type):
        # All folders are under detected_plates directory
        folder_path = os.path.abspath(os.path.join("detected_plates", f"detected_{folder_type}"))
        # Create the directory if it doesn't exist
        os.makedirs(folder_path, exist_ok=True)
        # Open the folder in File Explorer
        os.startfile(folder_path)

    def check_for_updates(self, manual=False):
        """
        Check for available updates.
        """
        update_info = self.updater.check_for_updates()
        if update_info:
            # Show pop-up notification if an update is available
            messagebox.showinfo(
                "Update Available",
                f"A new update (version {update_info['version']}) is available.\n"
                f"Changelog: {update_info['changelog']}"
            )
            # Proceed with update download and application
            success = self.updater.download_and_apply_update(update_info)
            if success:
                messagebox.showinfo("Update Successful", "The application has been updated successfully.")
                self.updater.restart_application()
            else:
                messagebox.showerror("Update Failed", "Failed to apply the update. Please try again later.")
        elif manual:
            # Notify the user if no updates are available only during manual check
            messagebox.showinfo(
                "No Updates Available",
                f"Your application is up to date.\nCurrent Version: {self.updater.current_version}"
            )
        else:
            print("No updates available.")
        
    def open_website(self):
        """Open the Khanfar Systems website in the default browser."""
        import webbrowser
        webbrowser.open('https://khanfar-systems.web.app/')

    def _update_telegram_bot(self):
        """Update the telegram bot configuration based on settings."""
        telegram_config = self.config.get("telegram", {})
        if telegram_config.get("enabled"):
            self.telegram_bot.set_token(telegram_config.get("bot_token", ""))
        else:
            self.telegram_bot.set_token("")

    def _create_gui(self):
        """Create the main GUI elements."""
        self.root.title(self._translate("window_title"))
        
        # Create menu
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=self._translate("menu_file"), menu=file_menu)
        file_menu.add_command(label=self._translate('video_source'),
                            command=self.show_video_source_config)
        file_menu.add_command(label=self._translate('cleanup_config'),
                            command=self.show_cleanup_config)
        file_menu.add_command(label=self._translate('telegram_config'),
                            command=self.show_telegram_config)
        file_menu.add_separator()
        file_menu.add_command(label=self._translate('menu_activate'),
                            command=lambda: ActivationDialog(self.root))
        file_menu.add_separator()
        file_menu.add_command(label=self._translate('menu_exit'), 
                            command=self.on_closing)

        # Settings menu
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=self._translate('settings_menu'), menu=settings_menu)
        settings_menu.add_command(label=self._translate('settings'),
                                command=self.show_settings)

        # Language menu
        language_menu = tk.Menu(settings_menu, tearoff=0)
        settings_menu.add_cascade(label=self._translate('language_menu'), menu=language_menu)
        language_menu.add_command(label=self._translate('english'),
                                command=lambda: self.change_language('en'))
        language_menu.add_command(label=self._translate('arabic'),
                                command=lambda: self.change_language('ar'))

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=self._translate('help_menu'), menu=help_menu)
        help_menu.add_command(label=self._translate('contact_us'), command=self.show_contact_us)
        help_menu.add_command(label=self._translate('how_to_use'), command=self.show_how_to_use)
        help_menu.add_command(label=self._translate('check_for_updates'), command=lambda: self.check_for_updates(manual=True))
        help_menu.add_separator()
        help_menu.add_command(label=self._translate('visit_website'), command=self.open_website)
        
        # Detected Pictures menu
        detected_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=self._translate('detected_pictures'), menu=detected_menu)
        detected_menu.add_command(label=self._translate('cars'), 
                                command=lambda: self.open_detection_folder("cars"))
        detected_menu.add_command(label=self._translate('persons'), 
                                command=lambda: self.open_detection_folder("persons"))
        detected_menu.add_command(label=self._translate('license_plates'), 
                                command=lambda: self.open_detection_folder("plates"))
        
        # Configure root for RTL support if Arabic
        if self.current_language == 'ar':
            self.root.tk.call('tk', 'scaling', 1.0)
            self.root.tk.call('encoding', 'system', 'utf-8')

        # Main container setup
        main_container = ttk.Frame(self.root)
        main_container.grid(row=0, column=0, sticky="nsew")

        # Add title label in top-left
        title_label = ttk.Label(main_container, text=self._translate('title'), 
                              font=('Helvetica', 16, 'bold'))
        title_label.grid(row=0, column=0, sticky="w", padx=10, pady=5)

        # Left panel
        left_panel = ttk.Frame(main_container)
        left_panel.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # Control frame
        self.control_frame = ttk.LabelFrame(left_panel, text=self._translate('controls'), padding="5")
        self.control_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # Settings frame
        self.settings_frame = ttk.LabelFrame(left_panel, text=self._translate('settings'), padding="5")
        self.settings_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # Counter frame
        self.counter_frame = ttk.LabelFrame(left_panel, text=self._translate('detection_counters'), padding="5")
        self.counter_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)

        # Create settings
        row = 0
        
        # Device selection
        ttk.Label(self.settings_frame, text=self._translate('processing_device')).grid(row=row, column=0)
        device_combo = ttk.Combobox(self.settings_frame, textvariable=self.device_var,
                                  values=["cpu", "cuda"], state="readonly", width=10)
        device_combo.grid(row=row, column=1)
        row += 1

        # Detection settings
        ttk.Label(self.settings_frame, text=self._translate('detection_settings')).grid(row=row, column=0, columnspan=2, pady=5)
        row += 1

        detection_frame = ttk.Frame(self.settings_frame)
        detection_frame.grid(row=row, column=0, columnspan=2, sticky="w", pady=5)
        
        self.person_var = tk.BooleanVar()
        ttk.Checkbutton(detection_frame, text=self._translate('person_detection'),
                       variable=self.person_var).pack(anchor="w")

        self.car_var = tk.BooleanVar()
        ttk.Checkbutton(detection_frame, text=self._translate('car_detection'),
                       variable=self.car_var).pack(anchor="w")

        self.plate_var = tk.BooleanVar()
        ttk.Checkbutton(detection_frame, text=self._translate('plate_detection'),
                       variable=self.plate_var).pack(anchor="w")
        
        row += 1

        # Sound settings
        self.sound_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.settings_frame, text=self._translate('enable_sound_notifications'),
                       variable=self.sound_var,
                       command=self._update_sound_settings).grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1

        # Detection delay
        ttk.Label(self.settings_frame, text=self._translate('detection_delay')).grid(row=row, column=0)
        self.detection_delay = tk.DoubleVar(value=3.0)
        ttk.Entry(self.settings_frame, textvariable=self.detection_delay, width=10).grid(row=row, column=1)
        row += 1

        # Thresholds
        ttk.Label(self.settings_frame, text=self._translate('confidence_threshold')).grid(row=row, column=0)
        self.conf_threshold = tk.DoubleVar()
        ttk.Entry(self.settings_frame, textvariable=self.conf_threshold, width=10).grid(row=row, column=1)
        row += 1

        ttk.Label(self.settings_frame, text=self._translate('ocr_threshold')).grid(row=row, column=0)
        self.ocr_threshold = tk.DoubleVar()
        ttk.Entry(self.settings_frame, textvariable=self.ocr_threshold, width=10).grid(row=row, column=1)
        row += 1

        # Performance settings
        ttk.Label(self.settings_frame, text=self._translate('performance_settings')).grid(row=row, column=0, columnspan=2, pady=5)
        row += 1

        self.low_resource_var = tk.BooleanVar()
        ttk.Checkbutton(self.settings_frame, text=self._translate('low_resource_mode'),
                       variable=self.low_resource_var).grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1

        ttk.Label(self.settings_frame, text=self._translate('skip_frames')).grid(row=row, column=0)
        self.skip_frames = tk.IntVar()
        ttk.Entry(self.settings_frame, textvariable=self.skip_frames, width=10).grid(row=row, column=1)
        row += 1

        # Save settings button
        ttk.Button(self.settings_frame, text=self._translate('save_settings'),
                  command=self._save_settings).grid(row=row, column=0, columnspan=2, pady=10)

        # Create counter labels
        counter_frame = ttk.Frame(self.counter_frame)
        counter_frame.pack(fill='x', padx=5, pady=5)
        self.blank_button = ttk.Button(counter_frame, text="", width=5)
        self.blank_button.pack(side='left', padx=5)
        ttk.Label(counter_frame, text=self._translate('total_persons')).pack(side='left', padx=10)
        self.person_counter_label = ttk.Label(counter_frame, text="0")
        self.person_counter_label.pack(side='left', padx=10)
        
        ttk.Label(counter_frame, text=self._translate('total_cars')).pack(side='left', padx=10)
        self.car_counter_label = ttk.Label(counter_frame, text="0")
        self.car_counter_label.pack(side='left', padx=10)
        
        ttk.Label(counter_frame, text=self._translate('total_plates')).pack(side='left', padx=10)
        self.plate_counter_label = ttk.Label(counter_frame, text="0")
        self.plate_counter_label.pack(side='left', padx=10)
        
        # Reset counter button
        ttk.Button(self.counter_frame, text=self._translate('reset_counters'), command=self._reset_counters).grid(row=1, column=0, columnspan=2, pady=5)

        # Video frame
        self.video_frame = ttk.LabelFrame(main_container, text=self._translate('video_feed'), padding="5")
        self.video_frame.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        self.video_label = ttk.Label(self.video_frame)
        self.video_label.grid(row=0, column=0)

        # Person detection frame (horizontal)
        self.person_detection_frame = ttk.LabelFrame(main_container, text=self._translate('person_detections'), padding="5")
        self.person_detection_frame.grid(row=2, column=1, sticky="ew", padx=5, pady=5)
        
        # Create horizontal container for person detections
        person_container = ttk.Frame(self.person_detection_frame)
        person_container.pack(fill="x", expand=True)
        
        # Initialize person detection frames
        self.person_frames = []
        for i in range(3):
            frame_container = ttk.Frame(person_container)
            frame_container.pack(side="left", padx=5, expand=True)
            label = ttk.Label(frame_container)
            label.pack()
            info = ttk.Label(frame_container, justify="left")
            info.pack()
            self.person_frames.append({"label": label, "info": info})

        # Right panel
        right_panel = ttk.Frame(main_container)
        right_panel.grid(row=1, column=2, rowspan=2, sticky="nsew", padx=5, pady=5)

        # License plate display
        plates_frame = ttk.LabelFrame(right_panel, text=self._translate('license_plates'), padding="5")
        plates_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Create plate displays
        self.plate_displays = []
        for i in range(3):
            plate_display = PlateDisplay(plates_frame)
            plate_display.grid(row=i, column=0, sticky="ew", padx=5, pady=2)
            self.plate_displays.append(plate_display)

        # Recent detections frame (for cars and plates)
        detections_frame = ttk.LabelFrame(right_panel, text=self._translate('recent_detections'), padding="5")
        detections_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # Create recent detection frames
        self.detection_frames = []
        for i in range(3):
            frame = ttk.LabelFrame(detections_frame, text=f"{self._translate('detection')} {i+1}", padding="5")
            frame.grid(row=i, column=0, sticky="nsew", padx=5, pady=5)
            label = ttk.Label(frame)
            label.grid(row=0, column=0, sticky="nsew")
            info_label = ttk.Label(frame, text=self._translate('no_detection'))
            info_label.grid(row=1, column=0, sticky="nsew")
            self.detection_frames.append({'frame': frame, 'label': label, 'info': info_label, 'current_type': None})

        # Control buttons
        self.start_button = ttk.Button(self.control_frame, text=self._translate('start_detection'),
                                     command=self.start_detection)
        self.start_button.grid(row=0, column=0, padx=5, pady=5)

        self.stop_button = ttk.Button(self.control_frame, text=self._translate('stop_detection'),
                                    command=self.stop_detection)
        self.stop_button.grid(row=0, column=1, padx=5, pady=5)

        # Open web server button
        self.open_web_button = ttk.Button(self.control_frame, text=self._translate('open_web_server'),
                                         command=self.open_web_server)
        self.open_web_button.grid(row=1, column=0, columnspan=3, pady=10)

        # Add LAN IP display label below the Open Web Server button
        self.lan_ip_label = ttk.Label(self.control_frame, text="")
        self.lan_ip_label.grid(row=2, column=0, columnspan=3, pady=10)

        # Update LAN IP display with actual IP address
        self.update_lan_ip_display()

        # Add Search for IP Cameras button below the LAN IP display
        self.search_cameras_button = ttk.Button(self.control_frame, text=self._translate('search_ip_cameras'), command=self.search_ip_cameras)
        self.search_cameras_button.grid(row=3, column=0, columnspan=3, pady=10)

        # Configure grid weights
        main_container.grid_columnconfigure(1, weight=3)
        main_container.grid_columnconfigure(2, weight=1)
        main_container.grid_rowconfigure(0, weight=1)

    def _update_button_states(self):
        """Update the states of start/stop buttons based on current running state"""
        if self.running:
            self.start_button.config(state="disabled")
            self.stop_button.config(state="normal")
        else:
            self.start_button.config(state="normal")
            self.stop_button.config(state="disabled")

    def _update_counter_displays(self):
        """Update all counter displays based on privacy mode"""
        if self.config.get_privacy_mode():
            self.person_counter_label.configure(text="Total Persons: ***")
            self.car_counter_label.configure(text="Total Cars: ***")
            self.plate_counter_label.configure(text="Total Plates: ***")
        else:
            self.person_counter_label.configure(text=f"Total Persons: {self.total_persons}")
            self.car_counter_label.configure(text=f"Total Cars: {self.total_cars}")
            self.plate_counter_label.configure(text=f"Total Plates: {self.total_plates}")

    def open_web_server(self):
        import webbrowser
        webbrowser.open('http://localhost:5000')

    def update_lan_ip_display(self):
        import socket
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        self.lan_ip_label.config(text=f"{local_ip}:5000")

    def search_ip_cameras(self):
        import socket
        from tkinter import messagebox
        import netifaces
        import threading

        def scan_ip(target_ip, rtsp_port, results):
            try:
                sock = socket.create_connection((target_ip, rtsp_port), timeout=0.5)
                results.append(target_ip)
                sock.close()
            except (socket.timeout, ConnectionRefusedError, OSError):
                pass

        def get_ip_range():
            interfaces = netifaces.interfaces()
            for interface in interfaces:
                addresses = netifaces.ifaddresses(interface)
                if netifaces.AF_INET in addresses:
                    for link in addresses[netifaces.AF_INET]:
                        ip = link['addr']
                        netmask = link.get('netmask', '255.255.255.0')
                        return ip, netmask
            return None, None

        def ip_to_int(ip):
            return sum([int(part) << (8 * i) for i, part in enumerate(reversed(ip.split('.')))])

        def int_to_ip(ip_int):
            return '.'.join([str((ip_int >> (8 * i)) & 0xFF) for i in reversed(range(4))])

        def get_ip_list(ip, netmask):
            ip_int = ip_to_int(ip)
            netmask_int = ip_to_int(netmask)
            network = ip_int & netmask_int
            broadcast = network | ~netmask_int & 0xFFFFFFFF
            return [int_to_ip(i) for i in range(network + 1, broadcast)]

        ip, netmask = get_ip_range()
        if not ip:
            messagebox.showerror(self._translate('camera_search_results'), self._translate('network_error'))
            return

        ip_list = get_ip_list(ip, netmask)
        rtsp_port = 554
        cameras = []

        threads = []
        results = []

        for target_ip in ip_list:
            thread = threading.Thread(target=scan_ip, args=(target_ip, rtsp_port, results))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        if results:
            def show_ip_list(ips):
                def on_select(event):
                    if listbox.curselection():
                        selected_ip = listbox.get(listbox.curselection())
                        if messagebox.askyesno(self._translate('ping_test'), f'{self._translate("ping_test_prompt")} {selected_ip}?'):
                            result = self.ping_ip(selected_ip)
                            messagebox.showinfo(self._translate('ping_test_result'), 
                                f"{self._translate('ping_test_result_message')} {selected_ip}: {self._translate(result.lower())}")

                popup = tk.Toplevel(self.root)
                popup.title(self._translate('camera_search_results'))
                listbox = tk.Listbox(popup, selectmode='single')
                listbox.pack(fill='both', expand=True)
                for ip in ips:
                    listbox.insert('end', ip)

                listbox.bind('<<ListboxSelect>>', on_select)
                ttk.Button(popup, text='Close', command=popup.destroy).pack()

            show_ip_list(results)
        else:
            messagebox.showinfo(self._translate('camera_search_results'), self._translate('no_cameras_found'))

    def ping_ip(self, ip):
        process = Popen(['ping', '-n', '4', ip], stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()
        if process.returncode == 0:
            # Parse the output for average time
            match = re.search(r'Average = (\d+)ms', stdout.decode())
            if match:
                avg_time = int(match.group(1))
                if avg_time < 50:
                    return 'Excellent'
                elif avg_time < 100:
                    return 'Good'
                else:
                    return 'Weak'
            else:
                return 'Ping test failed'
        else:
            return 'Ping test failed'

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

if __name__ == "__main__":
    setup_logging()
    root = tk.Tk()
    app = DetectionSystemGUI(root)
    root.title(app._translate('window_title'))  # Dynamically set title based on selected language
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.run()