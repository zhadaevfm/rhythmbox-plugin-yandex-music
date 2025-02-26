from gi.repository import GObject, RB, Peas, Gio, GLib, Gdk, Gtk
from yandex_music import Client
from widget import AuthDialog
from source import YandexMusicSource
from entry import YandexMusicEntry
import requests

class YandexMusic(GObject.Object, Peas.Activatable):
    object = GObject.property(type=GObject.Object)
    client = None

    def __init__(self):
        super(YandexMusic, self).__init__()

    def do_activate(self):
        print('Yandex.Music plugin activating')
        self.shell = self.object
        self.db = self.shell.props.db
        self.icon = Gio.FileIcon.new(Gio.File.new_for_path(self.plugin_info.get_data_dir()+'/yandex-music.svg'))
        schema_source = Gio.SettingsSchemaSource.new_from_directory(self.plugin_info.get_data_dir(), Gio.SettingsSchemaSource.get_default(), False)
        schema = schema_source.lookup('org.gnome.rhythmbox.plugins.yandex-music', False)
        self.settings = Gio.Settings.new_full(schema, None, None)
        if self.login_yandex():
            self.page_group = RB.DisplayPageGroup(shell=self.shell, id='yandex-music-playlist', name=_('Яндекс.Музыка'), category=RB.DisplayPageGroupType.TRANSIENT)
            self.shell.append_display_page(self.page_group, None)
            entry_type = YandexMusicEntry(self.shell, self.client, 'likes_')
            self.db.register_entry_type(entry_type)
            source = GObject.new(YandexMusicSource, shell=self.shell, name=_('Мне нравится'), entry_type=entry_type, plugin=self, icon=self.icon)
            source.setup(self.shell, self.client, 'likes_')
            self.shell.register_entry_type_for_source(source, entry_type)
            self.shell.append_display_page(source, self.page_group)
            Gdk.threads_add_idle(GLib.PRIORITY_DEFAULT_IDLE, self.load_users_playlists)
            Gdk.threads_add_idle(GLib.PRIORITY_DEFAULT_IDLE, self.load_users_likes_playlists)
            Gdk.threads_add_idle(GLib.PRIORITY_DEFAULT_IDLE, self.load_dashboard)

    def do_deactivate(self):
        print('Yandex.Music plugin deactivating')
        self.shell = None
        self.client = None
        self.db = None
        self.icon = None
        self.settings = None

    def load_users_playlists(self):
        if not self.client: return False
        playlists = self.client.users_playlists_list()
        iterator = 0
        for result in playlists:
            entry_type = YandexMusicEntry(self.shell, self.client, 'mepl'+str(iterator)+'_'+str(result.kind))
            source = GObject.new(YandexMusicSource, shell=self.shell, name=result.title, entry_type=entry_type, plugin=self, icon=self.icon)
            source.setup(self.shell, self.client, 'mepl'+str(iterator)+'_'+str(result.kind))
            self.shell.register_entry_type_for_source(source, entry_type)
            self.shell.append_display_page(source, self.page_group)
            iterator += 1
        return False

    def load_users_likes_playlists(self):
        if not self.client: return False
        page_group = RB.DisplayPageGroup(shell=self.shell, id='yandex-music-likes-playlists', name=_('Яндекс.Музыка')+': '+_('Мне нравится'), category=RB.DisplayPageGroupType.TRANSIENT)
        self.shell.append_display_page(page_group, None)
        playlists = self.client.users_likes_playlists()
        iterator = 0
        for result in playlists:
            if result.type != 'playlist': continue
            entry_type = YandexMusicEntry(self.shell, self.client, 'likepl'+str(iterator)+'_'+str(result.playlist.uid)+':'+str(result.playlist.kind))
            source = GObject.new(YandexMusicSource, shell=self.shell, name=result.playlist.title, entry_type=entry_type, plugin=self, icon=self.icon)
            source.setup(self.shell, self.client, 'likepl'+str(iterator)+'_'+str(result.playlist.uid)+':'+str(result.playlist.kind))
            self.shell.register_entry_type_for_source(source, entry_type)
            self.shell.append_display_page(source, page_group)
            iterator += 1
        return False

    def load_dashboard(self):
        if not self.client: return False
        page_group = RB.DisplayPageGroup(shell=self.shell, id='yandex-music-dashboard', name=_('Яндекс.Музыка')+': '+_('Потоки'), category=RB.DisplayPageGroupType.TRANSIENT)
        self.shell.append_display_page(page_group, None)
        dashboard = self.client.rotor_stations_dashboard()
        iterator = 0
        for result in dashboard.stations:
            entry_type = YandexMusicEntry(self.shell, self.client, 'feed'+str(iterator)+'_'+result.station.id.type+':'+result.station.id.tag)
            source = GObject.new(YandexMusicSource, shell=self.shell, name=result.station.name, entry_type=entry_type, plugin=self, icon=self.icon)
            source.setup(self.shell, self.client, 'feed'+str(iterator)+'_'+result.station.id.type+':'+result.station.id.tag)
            self.shell.register_entry_type_for_source(source, entry_type)
            self.shell.append_display_page(source, page_group)
            iterator += 1
        return False

    def login_yandex(self):
        token = self.settings.get_string('token')
        iterator = 0
        while not token and iterator < 5:
            window = AuthDialog(None)
            response = window.run()
            if (response == Gtk.ResponseType.OK):
                result = window.get_result()
                window.destroy()
                if result['login'] and result['password']:
                    token = self.generate_token(result['login'], result['password'])
                    if token:
                        self.settings.set_string('token', token)
            elif (response == Gtk.ResponseType.CANCEL):
                window.destroy()
                return False
            iterator += 1
        self.client = Client(token).init()
        return isinstance(self.client, Client)

    def generate_token(self, login, password):
        link_post = 'https://oauth.yandex.com/token'
        user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36'
        client_id = '23cabbbdc6cd418abb4b39c32c41195d'
        client_secret = '53bc75238f0c4d08a118e51fe9203300'
        header = {
            'user-agent': user_agent
        }
        try:
            request_post = f"grant_type=password&client_id={client_id}&client_secret={client_secret}&username={login}&password={password}"
            request_auth = requests.post(link_post, data=request_post, headers=header)
            if request_auth.status_code == 200:
                json_data = request_auth.json()
                token = json_data.get('access_token')
                return token
            else:
                print('Не удалось получить токен')
                print(request_auth.json())
        except requests.exceptions.ConnectionError:
            print('Не удалось отправить запрос на получение токена')
        return ''
