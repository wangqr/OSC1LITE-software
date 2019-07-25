#! /usr/bin/env python3.5

import wx
import threading
import time
import logging
import os
import matplotlib.pyplot as plt

import ok
import osc1lite

__version__ = '0.0.1'

logging.basicConfig(level=os.environ.get("LOGLEVEL", "DEBUG"))


class LabeledCtrl(wx.BoxSizer):
    def __init__(self, control, parent=None, ident=-1, label=''):
        wx.BoxSizer.__init__(self, wx.VERTICAL)
        self.Add(wx.StaticText(parent, ident, label), 1, wx.EXPAND)
        self.Add(control, 1, wx.EXPAND)


class ChannelCtrl:
    def __init__(self, waveform_choice: wx.Choice, trigger_choice: wx.Choice,
                 continuous_toggle: wx.ToggleButton, trigger_button: wx.Button,
                 stop_button: wx.Button, trigger_out_toggle: wx.ToggleButton):
        self.waveform_choice = waveform_choice
        self.trigger_choice = trigger_choice
        self.continuous_toggle = continuous_toggle
        self.trigger_button = trigger_button
        self.stop_button = stop_button
        self.trigger_out_toggle = trigger_out_toggle


class SquareWavePanel(wx.FlexGridSizer):
    def __init__(self, parent):
        wx.FlexGridSizer.__init__(self, 2, 4, 5, 5)
        for i in range(4):
            self.AddGrowableCol(i, 1)
        self.Add(wx.StaticText(parent, -1, 'Amplitude (\u03bcA)'), 0, wx.EXPAND)
        self.Add(wx.StaticText(parent, -1, 'Pulse Width (ms)'), 0, wx.EXPAND)
        self.Add(wx.StaticText(parent, -1, 'Period (ms)'), 0, wx.EXPAND)
        self.Add(wx.StaticText(parent, -1, 'Rise Time (ms)'), 0, wx.EXPAND)
        self.amp_text = wx.TextCtrl(parent, -1, '2000')
        self.Add(self.amp_text, 0, wx.EXPAND)
        self.pw_text = wx.TextCtrl(parent, -1, '100')
        self.Add(self.pw_text, 0, wx.EXPAND)
        self.period_text = wx.TextCtrl(parent, -1, '200')
        self.Add(self.period_text, 0, wx.EXPAND)
        self.rise_time_text = wx.TextCtrl(parent, -1, '0')
        self.Add(self.rise_time_text, 0, wx.EXPAND)

    def get_waveform(self) -> osc1lite.SquareWaveform:
        rise_time = float(self.rise_time_text.GetValue())
        mode = (0 if rise_time < .05 else
                1 if rise_time < .3 else
                2 if rise_time < .75 else 3 if rise_time < 1.5 else 4)
        return osc1lite.SquareWaveform(amp=float(self.amp_text.GetValue()),
                                       pw=float(self.pw_text.GetValue()) / 1000,
                                       period=float(
                                           self.period_text.GetValue()) / 1000,
                                       mode=mode)


class CustomWavePanel(wx.BoxSizer):
    def __init__(self, parent):
        wx.BoxSizer.__init__(self, wx.VERTICAL)
        self.Add(wx.StaticText(parent, -1, 'Custom Waveform File'), 0, wx.EXPAND)
        self.file_picker = wx.FilePickerCtrl(parent, -1, wildcard='*.cwave')
        self.file_picker.Bind(wx.EVT_FILEPICKER_CHANGED, self.on_file)
        self.Add(self.file_picker, 0, wx.EXPAND)
        self.wave = []

    def on_file(self, event: wx.Event):
        with open(self.file_picker.GetPath()) as fp:
            self.wave = [float(x) for x in fp.read().split()]

    def get_waveform(self) -> osc1lite.CustomWaveform:
        return osc1lite.CustomWaveform(self.wave)


class WaveFormPanel(wx.StaticBoxSizer):
    def __init__(self, parent, label):
        wx.StaticBoxSizer.__init__(self, wx.VERTICAL, parent, label)
        self.label = label
        common = wx.BoxSizer(wx.HORIZONTAL)
        waveform_type_choice = wx.Choice(parent, -1,
                                         choices=['Square Wave', 'Custom Wave'])
        waveform_type_choice.SetSelection(0)
        waveform_type_choice.Bind(wx.EVT_CHOICE, self.on_type)
        common.Add(LabeledCtrl(waveform_type_choice, parent,
                               -1, 'Waveform Type'), 0, wx.ALL, 3)
        self.num_of_pulses = wx.SpinCtrl(parent, -1, min=1, max=0xffff)
        common.Add(
            LabeledCtrl(self.num_of_pulses, parent, -1, 'Number of Pulses'),
            0, wx.ALL, 3)
        common.AddStretchSpacer(1)
        preview_button = wx.Button(parent, -1, 'Preview')
        preview_button.Bind(wx.EVT_BUTTON, self.on_preview)
        common.Add(preview_button, 0, wx.EXPAND | wx.ALL, 3)

        common.Add(wx.Button(parent, -1, 'Delete'), 0, wx.EXPAND | wx.ALL, 3)
        self.Add(common, 0, wx.EXPAND)
        self.p_square = SquareWavePanel(parent)
        self.p_custom = CustomWavePanel(parent)
        self.Add(self.p_square, 0, wx.EXPAND | wx.ALL, 3)
        self.Add(self.p_custom, 0, wx.EXPAND | wx.ALL, 3)
        self.Hide(self.p_custom)
        # self.Layout()
        self.detail = self.p_square

    def channel_info(self) -> osc1lite.ChannelInfo:
        wf = self.detail.get_waveform()
        return osc1lite.ChannelInfo(wf, n_pulses=self.num_of_pulses.GetValue())

    def on_preview(self, event: wx.Event):
        x_limit = 10
        n_pulses = self.num_of_pulses.GetValue()
        plt.figure(num='Preview for ' + self.label)
        wf = self.detail.get_waveform()
        if isinstance(wf, osc1lite.SquareWaveform):
            if wf.period <= 0:
                xs = [0, x_limit]
                ys = [0, 0]
            else:
                xs = [0]
                ys = [0]
                i = 0
                while xs[-1] < x_limit and i < n_pulses:
                    x_offset = xs[-1]
                    rise_time = (0, 0.1, 0.5, 1, 2)[wf.mode]
                    xs.extend([x_offset + rise_time,
                               x_offset + wf.pulse_width - rise_time,
                               x_offset + wf.pulse_width, x_offset + wf.period])
                    ys.extend([wf.amp, wf.amp, 0, 0])
                    i += 1
                if xs[-1] < x_limit:
                    xs.append(x_limit)
                    ys.append(0)
        elif isinstance(wf, osc1lite.CustomWaveform):
            xs = range(len(wf.wave))
            ys = wf.wave
        else:
            raise TypeError('Waveform type not supported')
        plt.plot(xs, ys)
        plt.xlabel('time (s)')
        plt.ylabel('amplitude (\u03bcA)')
        plt.show()

    def on_type(self, event: wx.Event):
        obj = event.GetEventObject()
        assert isinstance(obj, wx.Choice)
        if obj.GetSelection() == 0:  # Square Wave
            self.Hide(self.p_custom)
            self.Show(self.p_square)
            self.Layout()
            self.detail = self.p_square
        else:
            self.Hide(self.p_square)
            self.Show(self.p_custom)
            self.Layout()
            self.detail = self.p_custom


class MainFrame(wx.Frame):

    def device_lister(self) -> None:
        logging.getLogger('OSCGUI').debug('device_lister started')
        while self.device is None:
            devices = {}
            for i in range(self._dev.GetDeviceCount()):
                model = self._dev.GetDeviceListModel(i)
                serial = self._dev.GetDeviceListSerial(i)
                if model and serial:
                    devices[serial] = model
                else:
                    break
            if devices != self.devices:
                self.devices = devices
                curr = self.device_choice.GetString(
                    self.device_choice.GetSelection())
                if devices:
                    l_devices = list(devices)
                    self.device_choice.Set(l_devices)
                    try:
                        sel = l_devices.index(curr)
                    except ValueError:
                        sel = 0
                    self.device_choice.SetSelection(sel)
                    self.connect_button.Enable(True)
                else:
                    self.device_choice.Set(['[No connected devices]'])
                    self.device_choice.SetSelection(0)
                    self.connect_button.Enable(False)
            time.sleep(0.1)

    def device_watcher(self) -> None:
        logging.getLogger('OSCGUI').debug('device_watcher started')
        while self.device is not None:
            assert isinstance(self.device, osc1lite.OSC1Lite)
            if not self._dev.IsOpen():
                logging.getLogger('OSCGUI').warning(
                    'device closed unexpectedly')
                return
            warn = self.device.get_channel_warnings()
            for i in warn:
                logging.getLogger('OSCGUI').warning(
                    'Overlapped trigger detected on channel %d' % i)
            time.sleep(0.1)

    def __init__(self, parent=None, ident=-1):
        wx.Frame.__init__(self, parent, ident,
                          'OSC1Lite Stimulate GUI v' + __version__)
        self._dev = ok.okCFrontPanel()
        self.device = None
        self.devices = {}

        p = wx.Panel(self, -1)

        # Setup frame
        setup_sizer = wx.StaticBoxSizer(wx.HORIZONTAL, p, 'Setup')
        self.device_choice = wx.Choice(p, -1,
                                       choices=['[No connected devices]'])
        self.device_choice.SetSelection(0)
        self.device_choice.SetSize(self.device_choice.GetBestSize())
        self.connect_button = wx.Button(p, -1, 'Connect')
        self.connect_button.Enable(False)
        self.connect_button.Bind(wx.EVT_BUTTON, self.on_connect)
        self.thread = threading.Thread(target=self.device_lister, daemon=True)
        self.thread.start()
        setup_sizer.Add(LabeledCtrl(self.device_choice, p, -1,
                                    'Select your OSC1Lite'),
                        0, wx.EXPAND | wx.ALL, 3)
        setup_sizer.AddStretchSpacer(1)
        setup_sizer.Add(self.connect_button, 0, wx.EXPAND | wx.ALL, 3)

        left_box = wx.BoxSizer(wx.VERTICAL)
        left_box.Add(setup_sizer, 0, wx.EXPAND)
        left_box.AddSpacer(50)

        self.waveform_panels = [WaveFormPanel(p, 'Waveform %d' % (x + 1))
                                for x in range(4)]
        for wf in self.waveform_panels:
            left_box.Add(wf, 0, wx.EXPAND)

        channel_panel = wx.StaticBoxSizer(wx.VERTICAL, p)
        channel_box = wx.FlexGridSizer(7, 5, 5)
        self.channels_ui = []
        for i in range(1, 7):
            channel_box.AddGrowableCol(i, 1)
        for i in range(12):
            channel_box.Add(wx.StaticText(p, -1, 'Channel %2d' % i),
                            0, wx.ALIGN_CENTER_VERTICAL)

            waveform_choice = wx.Choice(p, -1,
                                        choices=['Waveform %d' % (x + 1) for x
                                                 in range(4)])
            waveform_choice.SetSelection(0)
            wrap_box = wx.BoxSizer(wx.HORIZONTAL)
            wrap_box.Add(waveform_choice, 1, wx.ALIGN_CENTER_VERTICAL)
            channel_box.Add(wrap_box, 0, wx.EXPAND)

            trigger_choice = wx.Choice(p, -1, choices=['PC trigger',
                                                       'External trigger'])
            trigger_choice.SetSelection(0)
            trigger_choice.Bind(wx.EVT_CHOICE, self.on_trigger_choice)

            wrap_box = wx.BoxSizer(wx.HORIZONTAL)
            wrap_box.Add(trigger_choice, 1, wx.ALIGN_CENTER_VERTICAL)
            channel_box.Add(wrap_box, 0, wx.EXPAND)

            continuous_toggle = wx.ToggleButton(p, -1, 'One-shot Mode')
            wrap_box = wx.BoxSizer(wx.HORIZONTAL)
            wrap_box.Add(continuous_toggle, 1, wx.ALIGN_CENTER_VERTICAL)
            channel_box.Add(wrap_box, 0, wx.EXPAND)

            trigger_button = wx.Button(p, -1, 'Trigger Channel #%d' % i)
            trigger_button.Enable(False)
            trigger_button.Bind(wx.EVT_BUTTON, self.on_trigger)
            wrap_box = wx.BoxSizer(wx.HORIZONTAL)
            wrap_box.Add(trigger_button, 1, wx.ALIGN_CENTER_VERTICAL)
            channel_box.Add(wrap_box, 0, wx.EXPAND)

            stop_button = wx.Button(p, -1, 'Stop Channel #%d' % i)
            stop_button.Enable(False)
            stop_button.Bind(wx.EVT_BUTTON, self.on_stop)
            wrap_box = wx.BoxSizer(wx.HORIZONTAL)
            wrap_box.Add(stop_button, 1, wx.ALIGN_CENTER_VERTICAL)
            channel_box.Add(wrap_box, 0, wx.EXPAND)

            trigger_out_toggle = wx.ToggleButton(p, -1, 'Trigger Out Disabled')
            trigger_out_toggle.Enable(False)
            wrap_box = wx.BoxSizer(wx.HORIZONTAL)
            wrap_box.Add(trigger_out_toggle, 1, wx.ALIGN_CENTER_VERTICAL)
            channel_box.Add(wrap_box, 0, wx.EXPAND | wx.LEFT, 5)

            self.channels_ui.append(
                ChannelCtrl(waveform_choice, trigger_choice, continuous_toggle,
                            trigger_button, stop_button, trigger_out_toggle))

            channel_box.AddGrowableRow(i, 1)
        self.Bind(wx.EVT_TOGGLEBUTTON, self.on_toggle)
        channel_panel.Add(channel_box, 1, wx.EXPAND)

        right_box = wx.BoxSizer(wx.VERTICAL)
        right_box.Add(channel_panel, 1, wx.EXPAND | wx.BOTTOM, 50)
        self.log_text = wx.TextCtrl(p, -1,
                                    style=wx.TE_MULTILINE | wx.TE_READONLY)
        sh = logging.StreamHandler(self.log_text)
        sh.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        sh.setFormatter(formatter)
        logging.getLogger().addHandler(sh)
        log_box = wx.StaticBoxSizer(wx.VERTICAL, p, 'Log')
        log_box.Add(self.log_text, 1, wx.EXPAND)
        clear_log_button = wx.Button(p, -1, 'Clear Log')
        clear_log_button.Bind(wx.EVT_BUTTON, self.on_clear_log)
        log_box.Add(clear_log_button, 0, wx.EXPAND)
        right_box.Add(log_box, 1, wx.EXPAND)

        box = wx.BoxSizer(wx.HORIZONTAL)
        box.Add(left_box, 0, wx.ALL, 5)
        box.AddSpacer(50)
        box.Add(right_box, 1, wx.EXPAND | wx.ALL, 5)
        p.SetSizer(box)
        box.Fit(p)
        self.Fit()

    def on_toggle(self, event: wx.Event):
        ident = event.GetId()
        obj = event.GetEventObject()
        assert isinstance(obj, wx.ToggleButton)
        for ch, x in enumerate(self.channels_ui):
            if ident == x.continuous_toggle.GetId():
                obj.SetLabel('Continuous Mode' if obj.GetValue()
                             else 'One-shot Mode')
                break
            elif ident == x.trigger_out_toggle.GetId():
                assert isinstance(self.device, osc1lite.OSC1Lite)
                self.device.set_trigger_out(ch, x.trigger_out_toggle.GetValue())
                obj.SetLabel('Trigger Out Enabled' if obj.GetValue()
                             else 'Trigger Out Disabled')
                break

    def on_trigger(self, event: wx.Event):
        ident = event.GetId()
        obj = event.GetEventObject()
        assert isinstance(obj, wx.Button)
        assert isinstance(self.device, osc1lite.OSC1Lite)
        for ch, x in enumerate(self.channels_ui):
            if ident == x.trigger_button.GetId():
                wf = x.waveform_choice.GetSelection()
                data = self.waveform_panels[wf].channel_info()
                data.ext_trig = x.trigger_choice.GetSelection()
                if x.continuous_toggle.GetValue():
                    data.n_pulses = 0
                self.device.set_channel(ch, data)
                if data.ext_trig == 0:
                    self.device.trigger_channel(ch)
                break

    def on_trigger_choice(self, event: wx.Event):
        ident = event.GetId()
        obj = event.GetEventObject()
        assert isinstance(obj, wx.Choice)
        for ch, x in enumerate(self.channels_ui):
            if ident == x.trigger_choice.GetId():
                if obj.GetSelection() == 0:  # PC trigger
                    x.trigger_button.SetLabel('Trigger Channel #%d' % ch)
                else:
                    x.trigger_button.SetLabel('Update Channel #%d' % ch)

    def on_stop(self, event: wx.Event):
        ident = event.GetId()
        obj = event.GetEventObject()
        assert isinstance(obj, wx.Button)
        assert isinstance(self.device, osc1lite.OSC1Lite)
        for ch, x in enumerate(self.channels_ui):
            if ident == x.stop_button.GetId():
                data = osc1lite.ChannelInfo(osc1lite.SquareWaveform())
                self.device.set_channel(ch, data)
                self.device.trigger_channel(ch)
                break

    def on_connect(self, event: wx.Event):
        if self.device is None:
            self.device_choice.Enable(False)
            self._dev.OpenBySerial(self.device_choice.GetString(
                self.device_choice.GetSelection()))
            self.device = osc1lite.OSC1Lite(self._dev)
            self.thread.join()
            self.device.configure(bit_file='OSC1_LITE_Control.bit',
                                  ignore_hash_error=True)
            self.device.reset()
            self.device.init_dac()
            self.device.enable_dac_output()
            self.connect_button.SetLabel('Disconnect')

            for x in self.channels_ui:
                x.trigger_button.Enable(True)
                x.stop_button.Enable(True)
                x.trigger_out_toggle.Enable(True)
            self.thread = threading.Thread(target=self.device_watcher,
                                           daemon=True)
            self.thread.start()
            logging.getLogger('OSCGUI').info('Connected')
        else:
            self._dev.Close()
            self.device = None
            self.thread.join()
            self.thread = threading.Thread(target=self.device_lister,
                                           daemon=True)
            self.thread.start()
            self.device_choice.Enable(True)
            self.connect_button.SetLabel('Connect')
            for x in self.channels_ui:
                x.trigger_button.Enable(False)
                x.stop_button.Enable(False)
                x.trigger_out_toggle.SetLabel('Trigger Out Disabled')
                x.trigger_out_toggle.SetValue(False)
                x.trigger_out_toggle.Enable(False)
            logging.getLogger('OSCGUI').info('Disconnected')

    def on_clear_log(self, event):
        self.log_text.Clear()


if __name__ == '__main__':
    app = wx.App()
    MainFrame().Show()
    exit(app.MainLoop())
