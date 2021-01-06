import gi
import time
import os
gi.require_version("Notify", "0.7")
gi.require_version("Gtk", "3.0")
from gi.repository import Notify, Gtk
from gi.repository import Gio, GLib, GObject, Peas
from gi.repository import RB
from pypresence import Presence
from status_prefs import discord_status_prefs

class discord_status_dev(GObject.Object, Peas.Activatable):
  GObject.type_register(discord_status_prefs)
  prefs = discord_status_prefs()
  settings = prefs.load_settings()
  show_notifs = settings["show_notifs"]

  try:
    Notify.init("Rhythmbox")
  except:
    print("Failed to init Notify. Is the notificaion service running?")

  is_streaming = False
  RPC = Presence("589905203533185064")
  connected = False
  gave_up = False

  try:
    RPC.connect()
    #try:
    #  if show_notifs:
    #    Notify.Notification.new("Rhythmbox Discord Status Plugin", "Connected to Discord").show()
    #    Notify.uninit()
    #except:
    #  print("Failed to init Notify. Is the notificaion service running?")
    connected = True
  except ConnectionRefusedError:
    try:
      if show_notifs:
        Notify.Notification.new("Rhythmbox Discord Status Plugin", "Failed to connect to Discord: ConnectionRefused. Is the client open?").show()
        Notify.uninit()
    except:
      print("Failed to init Notify. Is the notificaion service running?")

    if show_notifs:
      while not connected and not gave_up:
        dialog = Gtk.Dialog(title = "Discord Rhythmbox Status Plugin",
                            parent = None,
                            buttons = (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                       Gtk.STOCK_OK, Gtk.ResponseType.OK)
                           )

        hbox = Gtk.HBox()

        label = Gtk.Label("\nFailed to connect to the Discord client. Make sure that it is open. Retry?\n")
        hbox.pack_start(label, True, True, 0)

        dialog.vbox.pack_start(hbox, True, True, 0)
        dialog.vbox.show_all()

        response = dialog.run()

        if response == Gtk.ResponseType.OK:
          try:
            RPC.connect()
            connected = True
          except ConnectionRefusedError:
            print("Failed to retry connection to Discord")

        elif response == Gtk.ResponseType.CANCEL:
          gave_up = True
          dialog.destroy()

        else:
          pass

          dialog.destroy()

  __gtype_name__ = "DiscordStatusPlugin"
  object = GObject.property(type=GObject.Object)
  start_date = None
  playing_date = None
  is_playing = False
  def __init__(self):
    GObject.Object.__init__(self)

  def do_activate(self):
    shell = self.object
    sp = shell.props.shell_player
    self.psc_id  = sp.connect("playing-song-changed",
                              self.playing_entry_changed)
    self.pc_id   = sp.connect("playing-changed",
                              self.playing_changed)
    self.ec_id   = sp.connect("elapsed-changed",
                              self.elapsed_changed)
    self.pspc_id = sp.connect("playing-song-property-changed",
                              self.playing_song_property_changed)

  def do_deactivate(self):
    shell = self.object
    sp = shell.props.shell_player
    sp.disconnect(self.psc_id)
    sp.disconnect(self.pc_id)
    sp.disconnect(self.ec_id)
    sp.disconnect(self.pspc_id)
    self.RPC.clear(pid=os.getpid())
    self.RPC.close()

  def get_info(self, sp):
      album = None
      title = None
      artist = None
      duration = None

      if not sp.get_playing_entry().get_string(RB.RhythmDBPropType.ALBUM):
        album = ""
      else:
        album = " - %s" %(sp.get_playing_entry().get_string(RB.RhythmDBPropType.ALBUM))
      if album == " - Unknown":
        album = ""

      if not sp.get_playing_entry().get_string(RB.RhythmDBPropType.TITLE):
        title = "Unknown"
      else:
        title = sp.get_playing_entry().get_string(RB.RhythmDBPropType.TITLE)

      if not sp.get_playing_entry().get_string(RB.RhythmDBPropType.ARTIST):
        artist = "Unknown"
      else:
        artist = sp.get_playing_entry().get_string(RB.RhythmDBPropType.ARTIST)

      if not sp.get_playing_entry().get_ulong(RB.RhythmDBPropType.DURATION):
        duration = 0
      else:
        duration = sp.get_playing_entry().get_ulong(RB.RhythmDBPropType.DURATION)

      return [album, title, artist, duration]

  def playing_song_property_changed(self, sp, uri, property, old, newvalue):
      print("playing_song_property_changed: %s %s %s %s" %(uri, property, old, newvalue))

      info = self.get_info(sp)
      album = info[0]
      title = info[1]
      artist = info[2]

      details = "%s%s" %(artist, album)
      if details == "Unknown":
        details = title

      if property == "rb:stream-song-title":
        self.is_streaming = True
        self.update_streaming_rpc(details, newvalue)

  def update_streaming_rpc(self, info, d):
    if info == "Unknown":
      self.RPC.update(state=d[0:127], large_image="rhythmbox", small_image="play", small_text="Streaming", start=int(time.time()))
      return

    self.RPC.update(state=info[0:127], details=d[0:127], large_image="rhythmbox", small_image="play", small_text="Streaming", start=int(time.time()))

  def playing_entry_changed(self, sp, entry):
    if sp.get_playing_entry():
      self.start_date = int(time.time())
      self.playing_date = self.start_date
      info = self.get_info(sp)
      album = info[0]
      title = info[1]
      artist = info[2]
      duration = info[3]

      details="%s%s" %(artist, album)

      if duration == 0:
        self.update_streaming_rpc(details, title)
      if duration == 0 and self.is_streaming:
        return
      else:
        self.is_streaming = False

      self.is_playing = True

      start_time = int(time.time())
      pos = sp.get_playing_time().time
      end_time = start_time + duration - pos

      self.RPC.update(state=details[0:127], details=title[0:127], large_image="rhythmbox", small_image="play", small_text="Playing", start=start_time, end=end_time)

  def playing_changed(self, sp, playing):
    album = None
    title = None
    artist = None
    if sp.get_playing_entry():
      info = self.get_info(sp)
      album = info[0]
      title = info[1]
      artist = info[2]
      duration = info[3]

      details="%s%s" %(artist, album)

      if duration == 0 and not self.is_streaming:
        self.update_streaming_rpc(details, title)
      if duration == 0:
        return
      else:
        self.is_streaming = False

      start_time = int(time.time())
      pos = sp.get_playing_time().time
      end_time = start_time + duration - pos

    if playing:
      self.is_playing = True
      self.RPC.update(state=details[0:127], details=title[0:127], large_image="rhythmbox", small_image="play", small_text="Playing", start=start_time, end=end_time)
      return

    self.is_playing = False
    self.RPC.clear()

  def elapsed_changed(self, sp, elapsed):
    if not self.playing_date or not self.is_playing:
      return
    else:
      self.playing_date += 1
    if self.playing_date - elapsed == self.start_date:
      return
    else:
      if sp.get_playing_entry() and self.is_playing and not elapsed == 0:
        self.playing_date = self.start_date + elapsed
        info = self.get_info(sp)
        album = info[0]
        title = info[1]
        artist = info[2]
        duration = info[3]

        details="%s%s" %(artist, album)

        if duration == 0 and not self.is_streaming:
          self.update_streaming_rpc(details, title)
        if duration == 0:
          return
        else:
          self.is_streaming = False

        start_time = int(time.time())
        pos = sp.get_playing_time().time
        end_time = start_time + duration - pos

        self.RPC.update(state=details[0:127], details=title[0:127], large_image="rhythmbox", small_image="play", small_text="Playing", start=start_time, end=end_time)
