# -*- coding: utf-8 -*-
"""
    Copyright (C) 2017 Sebastian Golasch (plugin.video.netflix)
    Copyright (C) 2018 Caphm (original implementation module)
    Copyright (C) 2023 smirgol (adaption for plugin.video.crunchyroll)
    XML based dialogs

    SPDX-License-Identifier: MIT
    See LICENSES/MIT.md for more information.
"""

import time
import threading

import xbmc
import xbmcgui

# Navigation action constants (from Kodi stubs)
ACTION_PREVIOUS_MENU = 10
ACTION_PLAYER_STOP = 13
ACTION_NAV_BACK = 92
ACTION_NOOP = 999
ACTION_MOVE_LEFT = 1
ACTION_MOVE_RIGHT = 2
ACTION_MOVE_UP = 3
ACTION_MOVE_DOWN = 4
ACTION_SELECT_ITEM = 7
ACTION_ENTER = 135

CMD_CLOSE_DIALOG_BY_NOOP = 'AlarmClock(closedialog,Action(noop),{},silent)'


class SkipModalDialog(xbmcgui.WindowXMLDialog):
    """Dialog for skipping video parts (intro, [credits, recap], ...)"""

    def __init__(self, *args, **kwargs):
        self.seek_time = kwargs['seek_time']
        self.content_id = kwargs['content_id']
        self.label = kwargs['label']
        self.action_exit_keys_id = [ACTION_PREVIOUS_MENU,
                                    ACTION_PLAYER_STOP,
                                    ACTION_NAV_BACK,
                                    ACTION_NOOP]
        super().__init__(*args)

    def onInit(self):
        self.getControl(1000).setLabel(self.label)  # noqa

    def onClick(self, control_id):
        from resources.lib.videoplayer import update_playhead
        if control_id == 1000:
            xbmc.Player().seekTime(self.seek_time)
            try:
                update_playhead(self.content_id, int(self.seek_time))
            finally:
                self.close()

    def onAction(self, action):
        if action.getId() in self.action_exit_keys_id:
            self.close()


class DeviceActivationDialog(xbmcgui.WindowXMLDialog):
    """
    Device Code Activation Dialog for Crunchyroll Authentication

    Shows user code, verification URL, countdown timer, and handles background polling.
    """

    # Control IDs (must match XML layout)
    LABEL_USER_CODE = 1000
    LABEL_VERIFICATION_URL = 1001
    LABEL_COUNTDOWN = 1002
    LABEL_STATUS = 1003
    BUTTON_REFRESH = 1004
    BUTTON_CANCEL = 1005
    LABEL_TITLE = 1006
    LABEL_INSTRUCTION = 1007
    IMAGE_QR_CODE = 1009
    LABEL_QR_STATUS = 1010
    LABEL_QR_HEADER = 1011

    def __init__(self, *args, **kwargs):
        """
        Initialize Device Activation Dialog

        Required kwargs:
            device_code_data: Dict with user_code, device_code, verification_uri, expires_in
            api_instance: API instance for polling device token
        """
        self.device_code_data = kwargs.get('device_code_data')
        self.api_instance = kwargs.get('api_instance')

        # Dialog state
        self.return_value = None  # 'success', 'cancelled', 'expired', 'error'
        self.auth_result = None   # Authentication result data
        self.countdown_time = self.device_code_data.get('expires_in', 300)  # Default 5 minutes

        # Threading for background operations
        self.polling_thread = None
        self.timer_thread = None
        self.stop_polling = threading.Event()

        # Action handling
        self.action_exit_keys_id = [
            ACTION_PREVIOUS_MENU,
            ACTION_PLAYER_STOP,
            ACTION_NAV_BACK,
            ACTION_NOOP
        ]

        super().__init__(*args)

    def onInit(self):
        """Initialize dialog UI elements"""
        try:
            from .globals import G

            # Set translated static labels
            title_text = G.args.addon.getLocalizedString(30309)
            self.getControl(self.LABEL_TITLE).setLabel(title_text)

            instruction_text = G.args.addon.getLocalizedString(30310)
            self.getControl(self.LABEL_INSTRUCTION).setLabel(instruction_text)

            refresh_text = G.args.addon.getLocalizedString(30311)
            self.getControl(self.BUTTON_REFRESH).setLabel(refresh_text)

            cancel_text = G.args.addon.getLocalizedString(30312)
            self.getControl(self.BUTTON_CANCEL).setLabel(cancel_text)

            # Set user code display
            user_code = self.device_code_data.get('user_code', 'ERROR')
            self.getControl(self.LABEL_USER_CODE).setLabel(user_code)

            # Set verification URL
            verification_uri = self.device_code_data.get('verification_uri', 'https://www.crunchyroll.com/activate')
            visit_text = G.args.addon.getLocalizedString(30300) % verification_uri
            self.getControl(self.LABEL_VERIFICATION_URL).setLabel(visit_text)

            # Generate QR code for verification URL with user code
            user_code = self.device_code_data.get('user_code', '')
            if user_code:
                # Create URL with embedded user code for better mobile experience
                qr_url = f"{verification_uri}?user_code={user_code}&device=Android%20TV"
            else:
                qr_url = verification_uri
            self.set_qr(qr_url)

            # Set initial status
            status_text = G.args.addon.getLocalizedString(30301)
            self.getControl(self.LABEL_STATUS).setLabel(status_text)

            # set qr code header translation
            qr_header_text = G.args.addon.getLocalizedString(30313)
            self.getControl(self.LABEL_QR_HEADER).setLabel(qr_header_text)

            # Set initial countdown
            self._update_countdown_display()

            # Start background operations
            self._start_countdown_timer()
            self._start_polling()

        except Exception as e:
            from . import utils
            utils.crunchy_log(f"DeviceActivationDialog onInit error: {e}", xbmc.LOGERROR)
            self.return_value = 'error'
            self.close()

    def onAction(self, action):
        """Handle remote control and keyboard actions"""
        action_id = action.getId()

        if action_id in self.action_exit_keys_id:
            # User wants to cancel
            self._cancel_activation()

    def onClick(self, control_id):
        """Handle button clicks"""
        if control_id == self.BUTTON_REFRESH:
            self._refresh_device_code()
        elif control_id == self.BUTTON_CANCEL:
            self._cancel_activation()

    def _start_countdown_timer(self):
        """Start countdown timer in background thread"""
        def countdown_worker():
            while not self.stop_polling.is_set() and self.countdown_time > 0:
                time.sleep(1)
                self.countdown_time -= 1
                # Update UI on main thread
                xbmc.executebuiltin('SetProperty(update_countdown,1,Home)')
                self._update_countdown_display()

            # Timer expired
            if self.countdown_time <= 0:
                self._handle_timeout()

        self.timer_thread = threading.Thread(target=countdown_worker, daemon=True)
        self.timer_thread.start()

    def _start_polling(self):
        """Start device token polling in background thread"""
        def polling_worker():
            from . import utils
            poll_interval = 5  # Start with 5 seconds

            while not self.stop_polling.is_set() and self.countdown_time > 0:
                time.sleep(poll_interval)

                if self.stop_polling.is_set():
                    break

                try:
                    # Poll device token
                    device_code = self.device_code_data.get('device_code')
                    result = self.api_instance.poll_device_token(device_code)

                    if result['status'] == 'success':
                        # Authentication successful!
                        self.auth_result = result['data']
                        self._handle_success()
                        break
                    elif result['status'] == 'expired':
                        self._handle_expired()
                        break
                    elif result['status'] == 'error':
                        self._handle_error(result.get('message', 'Unknown error'))
                        break
                    # elif result['status'] == 'pending': continue polling

                    # Implement exponential backoff (max 30 seconds)
                    poll_interval = min(poll_interval * 1.2, 30)

                except Exception as e:
                    utils.crunchy_log(f"Device token polling error: {e}")
                    # Continue polling, network errors are recoverable

        self.polling_thread = threading.Thread(target=polling_worker, daemon=True)
        self.polling_thread.start()

    def _update_countdown_display(self):
        """Update countdown timer display"""
        try:
            from .globals import G
            minutes = self.countdown_time // 60
            seconds = self.countdown_time % 60
            countdown_text = G.args.addon.getLocalizedString(30302) % (minutes, seconds)
            self.getControl(self.LABEL_COUNTDOWN).setLabel(countdown_text)
        except:
            pass  # UI might not be ready yet

    def _refresh_device_code(self):
        """Request new device code"""
        try:
            from .globals import G

            # Stop current operations
            self.stop_polling.set()

            # Wait for existing threads to finish
            current_thread = threading.current_thread()

            # Join polling thread if it exists and we're not in it
            if (self.polling_thread and
                self.polling_thread.is_alive() and
                current_thread != self.polling_thread):
                self.polling_thread.join(timeout=1.0)

            # Join timer thread if it exists and we're not in it
            if (self.timer_thread and
                self.timer_thread.is_alive() and
                current_thread != self.timer_thread):
                self.timer_thread.join(timeout=1.0)

            # Request new device code
            new_code_data = self.api_instance.request_device_code()
            if new_code_data:
                self.device_code_data = new_code_data
                self.countdown_time = new_code_data.get('expires_in', 300)
                self.stop_polling.clear()

                # Update UI
                self.getControl(self.LABEL_USER_CODE).setLabel(new_code_data.get('user_code', 'ERROR'))
                refresh_status = G.args.addon.getLocalizedString(30303)
                self.getControl(self.LABEL_STATUS).setLabel(refresh_status)

                # Regenerate QR code with new data
                verification_uri = new_code_data.get('verification_uri', 'https://www.crunchyroll.com/activate')
                new_user_code = new_code_data.get('user_code', '')
                if new_user_code:
                    qr_url = f"{verification_uri}?user_code={new_user_code}&device=Android%20TV"
                else:
                    qr_url = verification_uri
                self.set_qr(qr_url)

                # Restart operations
                self._start_countdown_timer()
                self._start_polling()
            else:
                error_text = G.args.addon.getLocalizedString(30307)
                self._handle_error(error_text)

        except Exception as e:
            from . import utils
            utils.crunchy_log(f"Refresh device code error: {e}")
            error_text = G.args.addon.getLocalizedString(30308)
            self._handle_error(error_text)

    def _cancel_activation(self):
        """Cancel the activation process"""
        self.stop_polling.set()
        self.return_value = 'cancelled'
        self.close()

    def _handle_success(self):
        """Handle successful authentication"""
        self.stop_polling.set()
        try:
            from .globals import G
            success_text = G.args.addon.getLocalizedString(30304)
            self.getControl(self.LABEL_STATUS).setLabel(success_text)
        except:
            pass  # UI might be closing
        self.return_value = 'success'

        # Close dialog immediately - don't try to join threads from within thread
        self.close()

    def _handle_timeout(self):
        """Handle code expiration timeout"""
        self.stop_polling.set()
        from .globals import G
        expired_text = G.args.addon.getLocalizedString(30305)
        self.getControl(self.LABEL_STATUS).setLabel(expired_text)
        self.return_value = 'expired'

    def _handle_expired(self):
        """Handle expired code from server"""
        self.stop_polling.set()
        from .globals import G
        expired_text = G.args.addon.getLocalizedString(30305)
        self.getControl(self.LABEL_STATUS).setLabel(expired_text)
        self.return_value = 'expired'

    def _handle_error(self, error_message):
        """Handle authentication errors"""
        self.stop_polling.set()
        from .globals import G
        error_text = G.args.addon.getLocalizedString(30306) % error_message
        self.getControl(self.LABEL_STATUS).setLabel(error_text)
        self.return_value = 'error'

    def set_qr(self, qr_url):
        """Generate and display QR code for the given URL"""
        if not qr_url:
            self._update_qr_status("No URL provided for QR code")
            return

        try:
            from . import utils
            import os
            import time as _t
            import struct
            import zlib
            import xbmc

            # Try to import pyqrcode module
            _pyqrcode = None
            try:
                from resources.modules import pyqrcode as _pyqrcode
            except Exception:
                try:
                    from ..modules import pyqrcode as _pyqrcode
                except Exception:
                    try:
                        import sys
                        addon_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                        if addon_root and addon_root not in sys.path:
                            sys.path.insert(0, addon_root)
                        from resources.modules import pyqrcode as _pyqrcode
                    except Exception:
                        utils.crunchy_log("[Crunchyroll] Failed to import pyqrcode module", xbmc.LOGERROR)
                        self._update_qr_status("PyQRCode module not found. Use the code above.")
                        return

            # Helper function for PNG generation
            def _chunk(fh, chunk_type, data):
                """Write a PNG chunk"""
                fh.write(struct.pack('>I', len(data)))
                fh.write(chunk_type)
                fh.write(data)
                crc = zlib.crc32(chunk_type + data) & 0xffffffff
                fh.write(struct.pack('>I', crc))

            def _write_png_gray(path, qr_rows, width, height):
                """Write grayscale PNG file for QR code"""
                import xbmcvfs
                with xbmcvfs.File(path, 'wb') as fh:
                    # PNG signature
                    fh.write(b'\x89PNG\r\n\x1a\n')
                    # IHDR chunk
                    ihdr = struct.pack('>IIBBBBB', width, height, 8, 0, 0, 0, 0)
                    _chunk(fh, b'IHDR', ihdr)
                    # IDAT chunk
                    scanlines = []
                    for row in qr_rows:
                        scanline = bytearray([0])  # No filter
                        scanline.extend(row)
                        scanlines.append(bytes(scanline))
                    idat_data = zlib.compress(b''.join(scanlines))
                    _chunk(fh, b'IDAT', idat_data)
                    # IEND chunk
                    _chunk(fh, b'IEND', b'')

            try:
                # Generate QR matrix
                qr = _pyqrcode.create(qr_url)
                qr_matrix = qr.code

                # Scale factor for readability (6 pixels per module)
                scale = 6
                img_size = len(qr_matrix) * scale

                # Create scaled pixel data (grayscale)
                rows = []
                for matrix_row in qr_matrix:
                    # Create scaled rows
                    for _ in range(scale):
                        pixel_row = []
                        for cell in matrix_row:
                            # Convert QR cell to grayscale: 1 -> black (0), 0 -> white (255)
                            color = 0 if cell == 1 else 255
                            pixel_row.extend([color] * scale)
                        rows.append(pixel_row)

                # Generate temporary file path
                import xbmc
                import xbmcvfs

                # Use Kodi's temp directory
                temp_dir = xbmcvfs.translatePath('special://temp/')
                qr_filename = f"crunchyroll_qr_{int(_t.time())}.png"
                qr_path = os.path.join(temp_dir, qr_filename)

                # Write PNG file
                _write_png_gray(qr_path, rows, img_size, img_size)

            except Exception as e_gen:
                utils.crunchy_log(f"[Crunchyroll] QR code generation failed: {e_gen}", xbmc.LOGERROR)
                self._update_qr_status("Unable to generate QR code. Use the code above.")
                return

            # Check if file was created successfully
            if xbmcvfs.exists(qr_path):
                try:
                    # Set QR image in UI
                    self.getControl(self.IMAGE_QR_CODE).setImage(qr_path)
                    self._update_qr_status("QR code ready")
                    utils.crunchy_log(f"[Crunchyroll] QR code generated: {qr_path}")

                    # Store path for cleanup
                    if not hasattr(self, '_qr_temp_files'):
                        self._qr_temp_files = []
                    self._qr_temp_files.append(qr_path)

                except Exception as e_ui:
                    utils.crunchy_log(f"[Crunchyroll] Failed to set QR image: {e_ui}", xbmc.LOGERROR)
                    self._update_qr_status("QR code generated but display failed")
                    try:
                        xbmcvfs.delete(qr_path)
                    except Exception:
                        pass
            else:
                utils.crunchy_log("[Crunchyroll] QR file does not exist!", xbmc.LOGERROR)
                self._update_qr_status("QR file missing")

        except Exception as e:
            utils.crunchy_log(f"[Crunchyroll] Error setting QR code: {e}", xbmc.LOGERROR)
            self._update_qr_status("QR code error")

    def _update_qr_status(self, status):
        """Update QR status text"""
        try:
            self.getControl(self.LABEL_QR_STATUS).setLabel(status)
        except Exception:
            pass

    def _cleanup_qr_files(self):
        """Clean up temporary QR files"""
        if hasattr(self, '_qr_temp_files'):
            import xbmcvfs
            for qr_path in self._qr_temp_files:
                try:
                    if xbmcvfs.exists(qr_path):
                        xbmcvfs.delete(qr_path)
                except Exception:
                    pass
            self._qr_temp_files = []

    def close(self):
        """Clean up when closing dialog"""
        self.stop_polling.set()

        # Clean up QR temporary files
        self._cleanup_qr_files()

        # Don't join threads if we're being called from within a thread
        # (this prevents "cannot join current thread" error)
        current_thread = threading.current_thread()

        # Only try to join if we're not being called from our own worker threads
        if (self.polling_thread and
            self.polling_thread.is_alive() and
            current_thread != self.polling_thread):
            self.polling_thread.join(timeout=0.5)

        if (self.timer_thread and
            self.timer_thread.is_alive() and
            current_thread != self.timer_thread):
            self.timer_thread.join(timeout=0.5)

        super().close()


def show_device_activation_dialog(device_code_data, api_instance):
    """
    Show device activation dialog for Crunchyroll authentication

    Args:
        device_code_data: Dict with user_code, device_code, verification_uri, expires_in
        api_instance: API instance for device token polling

    Returns:
        Dict with status and data:
        - {"status": "success", "auth_result": {...}} - Authentication successful
        - {"status": "cancelled"} - User cancelled
        - {"status": "expired"} - Code expired
        - {"status": "error", "message": "..."} - Error occurred
    """
    try:
        from .globals import G

        # Create and show dialog
        dialog = DeviceActivationDialog(
            'plugin-video-crunchyroll-activation.xml',
            G.args.addon.getAddonInfo('path'),
            'default',
            '1080i',
            device_code_data=device_code_data,
            api_instance=api_instance
        )

        dialog.doModal()

        # Get result from dialog
        result_status = getattr(dialog, 'return_value', 'error')
        auth_result = getattr(dialog, 'auth_result', None)

        # Clean up dialog
        del dialog

        # Return structured result
        if result_status == 'success' and auth_result:
            return {"status": "success", "auth_result": auth_result}
        elif result_status == 'cancelled':
            return {"status": "cancelled"}
        elif result_status == 'expired':
            return {"status": "expired"}
        else:
            return {"status": "error", "message": "Dialog returned unexpected status"}

    except Exception as e:
        from . import utils
        utils.crunchy_log(f"Device activation dialog error: {e}", xbmc.LOGERROR)
        utils.log_error_with_trace("Device activation dialog failed", show_notification=True)
        return {"status": "error", "message": f"Dialog error: {str(e)}"}


def show_modal_dialog(dialog_class, xml_filename, **kwargs):
    dialog = dialog_class(xml_filename, kwargs.get('addon_path'), 'default', '1080i', **kwargs)
    minutes = kwargs.get('minutes', 0)
    seconds = kwargs.get('seconds', 0)
    if minutes > 0 or seconds > 0:
        # Bug in Kodi AlarmClock function, if only the seconds are passed
        # the time conversion inside the function multiply the seconds by 60
        if seconds > 59 and minutes == 0:
            alarm_time = time.strftime('%M:%S', time.gmtime(seconds))
        else:
            alarm_time = f'{minutes:02d}:{seconds:02d}'
        xbmc.executebuiltin(CMD_CLOSE_DIALOG_BY_NOOP.format(alarm_time))

    dialog.doModal()

    if hasattr(dialog, 'return_value'):
        return dialog.return_value
    return None
