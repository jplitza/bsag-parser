#!/usr/bin/python
# -*- coding: utf-8 -*-

import datetime
from threading import Thread
import gobject
import dbus
try:
    import gconf
except ImportError:
    import gnome.gconf as gconf
import gtk
import gobject
import hildon
import conic
import bsag as backend

gobject.threads_init()
gtk.gdk.threads_init()

def lock_on_empty(widget, target):
    target.set_sensitive(widget.get_text() != "")

class SearchForm:
    GCONF_PATH = '/apps/bsag/'

    def __init__(self, conic = None):
        self.conic = conic
        # TODO: do this nice
        favicon = "/usr/share/icons/hicolor/48x48/hildon/general_mybookmarks_folder.png"

        self.gconf = gconf.client_get_default()
        if len(self.get_favourites()) == 0:
            self.gconf.set_list(self.GCONF_PATH + 'favourites',
                                gconf.VALUE_STRING,
                                ['Bremen, Hauptbahnhof']
                               )

        self.default_station = self.gconf.get_string(self.GCONF_PATH + 'default_station')
        if self.default_station == None:
            self.gconf.set_string(self.GCONF_PATH + 'default_station', 'Hauptbahnhof')
            self.default_station = 'Hauptbahnhof'

        self.default_city = self.gconf.get_string(self.GCONF_PATH + 'default_city')
        if self.default_city == None:
            self.gconf.set_string(self.GCONF_PATH + 'default_city', 'Bremen')
            self.default_city = 'Bremen'

        self.program = hildon.Program.get_instance()
        self.win = hildon.StackableWindow()
        self.win.set_title("BSAG")
        self.win.connect("destroy", gtk.main_quit)

        menu = hildon.AppMenu()
        settingsbutton = gtk.Button("Einstellungen")
        settingsbutton.connect("clicked", self.settings_dialog)
        menu.append(settingsbutton)
        menu.show_all()
        self.win.set_app_menu(menu)

        self.pan = hildon.PannableArea()
        self.form = gtk.VBox()
        table = gtk.Table(4, 4, False)


        self.origin_station = hildon.Entry(
            gtk.HILDON_SIZE_FINGER_HEIGHT)
        self.origin_station.connect("activate", self.search_activated)
        table.attach(self.origin_station, 1, 2, 0, 1)

        self.origin_city = hildon.Entry(
            gtk.HILDON_SIZE_FINGER_HEIGHT)
        self.origin_city.connect("activate", self.search_activated)
        table.attach(self.origin_city, 2, 3, 0, 1)

        depfav = hildon.Button(gtk.HILDON_SIZE_FINGER_HEIGHT,
            hildon.BUTTON_ARRANGEMENT_VERTICAL,
            title = "")
        depfav.set_image(gtk.image_new_from_file(favicon))
        depfav.connect("clicked", self.favourite_selector, (self.origin_station, self.origin_city))
        table.attach(depfav, 0, 1, 0, 1, gtk.FILL, gtk.FILL)

        self.destination_station = hildon.Entry(
            gtk.HILDON_SIZE_FINGER_HEIGHT)
        self.destination_station.connect("activate", self.search_activated)
        self.destination_station.set_placeholder("Zielhaltestelle")
        table.attach(self.destination_station, 1, 2, 1, 2)

        self.destination_city = hildon.Entry(
            gtk.HILDON_SIZE_FINGER_HEIGHT)
        self.destination_city.connect("activate", self.search_activated)
        table.attach(self.destination_city, 2, 3, 1, 2)

        self.origin_city.connect("changed", self.placeholder_changer, self.destination_city, "Stadt (%s)", self.default_city)

        arrfav = hildon.Button(gtk.HILDON_SIZE_FINGER_HEIGHT,
            hildon.BUTTON_ARRANGEMENT_VERTICAL,
            title = "")
        arrfav.set_image(gtk.image_new_from_file(favicon))
        arrfav.connect("clicked", self.favourite_selector, (self.destination_station, self.destination_city))
        table.attach(arrfav, 0, 1, 1, 2, gtk.FILL, gtk.FILL)

        switcher = hildon.Button(gtk.HILDON_SIZE_AUTO,
            hildon.BUTTON_ARRANGEMENT_VERTICAL,
            title = "<>")
        switcher.connect("clicked", self.switch_deparr)
        table.attach(switcher, 3, 4, 0, 2, gtk.FILL, gtk.FILL)

        self.deparr = hildon.GtkToggleButton(
            gtk.HILDON_SIZE_FINGER_HEIGHT)
        self.deparr.connect("clicked", lambda widget: widget.set_label("ab" if widget.get_active() else "an"))
        self.deparr.set_active(True)
        table.attach(self.deparr, 0, 1, 2, 3, gtk.FILL, gtk.FILL)

        self.date = hildon.DateButton(
            gtk.HILDON_SIZE_FINGER_HEIGHT,
            hildon.BUTTON_ARRANGEMENT_VERTICAL)
        self.date.set_alignment(0, 0, 0, 0)
        table.attach(self.date, 1, 2, 2, 3)

        self.time = hildon.TimeButton(
            gtk.HILDON_SIZE_FINGER_HEIGHT,
            hildon.BUTTON_ARRANGEMENT_VERTICAL)
        self.time.set_alignment(0, 0, 0, 0)
        table.attach(self.time, 2, 3, 2, 3)

        self.now = hildon.GtkToggleButton(
            gtk.HILDON_SIZE_FINGER_HEIGHT)
        self.now.set_label("Jetzt")
        self.now.connect("toggled", self.now_toggled)
        self.now.set_active(True)
        table.attach(self.now, 3, 4, 2, 3, gtk.FILL, gtk.FILL)

        self.submit = hildon.Button(gtk.HILDON_SIZE_FINGER_HEIGHT,
            hildon.BUTTON_ARRANGEMENT_VERTICAL,
            title = "Suche starten")
        self.submit.connect("clicked", self.search_activated)
        table.attach(self.submit, 0, 4, 3, 4)

        lock_on_empty(self.destination_station, self.submit)
        self.destination_station.connect("changed", lock_on_empty, self.submit)
        self.update_placeholders()

        self.form.pack_start(table, False, False, 0)
        self.pan.add_with_viewport(self.form)
        self.win.add(self.pan)

        self.win.show_all()

    def placeholder_changer(self, widget, target, text, default):
        target.set_placeholder(text % (widget.get_text() if len(widget.get_text()) > 0 else default))

    def update_placeholders(self):
        self.origin_station.set_placeholder("Starthaltestelle (%s)" % self.default_station)
        self.origin_city.set_placeholder("Stadt (%s)" % self.default_city)
        self.placeholder_changer(self.origin_city, self.destination_city, "Stadt (%s)", self.default_city)

    def get_favourites(self):
        return [backend.Station(name) for name in
            self.gconf.get_list(self.GCONF_PATH + 'favourites',
                                gconf.VALUE_STRING
        )]

    def search_activated(self, widget = None):
        thread = Thread(target=self.do_search)
        thread.start()
        hildon.hildon_gtk_window_set_progress_indicator(self.win, 1)

    def do_search(self):
        try:
            if self.now.get_active():
                date = datetime.datetime.now()
            else:
                date = self.date.get_date()
                time = self.time.get_time()
                date = datetime.datetime(date[0], date[1]+1, date[2], time[0], time[1])
            origin_station = self.origin_station.get_text()
            if origin_station == "":
                origin_station = self.default_station
            origin_city = self.origin_city.get_text()
            if origin_city == "":
                origin_city = self.default_city
            destination_city = self.destination_city.get_text()
            if destination_city == "":
                destination_city = self.default_city
            self.request = backend.Request(
                origin=backend.Station(origin_station, origin_city),
                destination=backend.Station(self.destination_station.get_text(), destination_city),
                date=date,
                deparr="dep" if self.deparr.get_active() else "arr"
            )
        except backend.AmbiguityException, e:
            self.amb = e
        except IOError:
            gobject.idle_add(self.conic_handler, priority=gobject.PRIORITY_DEFAULT)
        except (AttributeError, TypeError):
            self.errmsg = 'Keine Haltestelle gefunden!'
        finally:
            gobject.idle_add(self.present_results, priority=gobject.PRIORITY_DEFAULT)

    def conic_handler(self, connection = None, event = None):
        if not event:
            if self.conic:
                # establish internet connection
                self.conic.connect("connection-event", self.conic_handler)
                assert(self.conic.request_connection(conic.CONNECT_FLAG_NONE))
        elif event.get_status() == conic.STATUS_CONNECTED:
            self.search_activated()

    @staticmethod
    def selector_from_list(l):
        selector = hildon.TouchSelector(text = True)
        for item in l:
            selector.append_text(str(item))
        return selector

    def present_results(self):
        hildon.hildon_gtk_window_set_progress_indicator(self.win, 0)
        if hasattr(self, "request"):
            self.resultview = ResultView(self.request)
            del self.request
        elif hasattr(self, "amb"):
            if hasattr(self, self.amb.field):
                self.picker_dialog = hildon.PickerDialog(self.win)
                selector = self.selector_from_list([str(a) for a in self.amb.options])
                self.picker_dialog.set_selector(selector)
                selector.connect("changed", self.resolve_amb, self.amb.field)
                self.picker_dialog.set_title(self.amb.field)
                self.picker_dialog.show_all()
            del self.amb
        elif hasattr(self, "errmsg"):
            hildon.hildon_banner_show_information(self.win, "", self.errmsg)
            del self.errmsg

    def resolve_amb(self, widget, data, field):
        getattr(self, field).set_text(widget.get_current_text())
        self.picker_dialog.destroy()
        del self.picker_dialog
        self.search_activated()

    def favourite_selector(self, widget, target):
        self.favourite_dialog = hildon.PickerDialog(self.win)
        selector = self.selector_from_list(self.get_favourites())
        self.favourite_dialog.set_selector(selector)
        selector.connect("changed", self.select_favourite, target)
        self.favourite_dialog.set_title("Favorit auswählen")
        self.favourite_dialog.show_all()

    def select_favourite(self, widget, data, field):
        (store, it) = widget.get_selected(0)
        selected = backend.Station(store.get_value(it, 0))
        field[0].set_text(selected.station)
        field[1].set_text(selected.city)
        self.favourite_dialog.destroy()
        del self.favourite_dialog

    def settings_dialog(self, widget = None):
        self.SettingsDialog(self)

    class SettingsDialog:
        def __init__(self, parent):
            self.parent = parent

            self.dialog = gtk.Dialog("Einstellungen", parent.win, 0,
                (gtk.STOCK_DELETE, 257, "Als Heimat", 258, gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))

            addicon = "/usr/share/icons/hicolor/48x48/hildon/general_add.png"
            hbox = gtk.HBox()
            new_favourite_station = hildon.Entry(gtk.HILDON_SIZE_FINGER_HEIGHT)
            new_favourite_station.set_placeholder("Neuer Favorit")
            hbox.pack_start(new_favourite_station)

            new_favourite_city = hildon.Entry(gtk.HILDON_SIZE_FINGER_HEIGHT)
            new_favourite_city.set_placeholder("Stadt (%s)" % parent.default_city)
            hbox.pack_start(new_favourite_city)

            new_favourite_button = hildon.Button(gtk.HILDON_SIZE_FINGER_HEIGHT,
                hildon.BUTTON_ARRANGEMENT_VERTICAL,
                title = "")
            new_favourite_button.set_image(gtk.image_new_from_file(addicon))
            new_favourite_button.connect("clicked", self.new_favourite,
                    new_favourite_station, new_favourite_city)
            new_favourite_button.connect("activate", self.new_favourite,
                    new_favourite_station, new_favourite_city)
            new_favourite_button.connect("activate", self.new_favourite,
                    new_favourite_station, new_favourite_city)
            hbox.pack_start(new_favourite_button, False)

            new_favourite_station.connect("changed", lock_on_empty, new_favourite_button)
            lock_on_empty(new_favourite_station, new_favourite_button)

            self.dialog.vbox.pack_start(hbox)

            self.selector = hildon.TouchSelector()
            model = gtk.ListStore(str, gobject.TYPE_PYOBJECT)
            for station in parent.get_favourites():
                model.append([str(station), station])
            self.selector.append_text_column(model, False)
            self.selector.set_size_request(-1, 230)
            self.selector.set_column_selection_mode(hildon.TOUCH_SELECTOR_SELECTION_MODE_MULTIPLE)
            self.selector.unselect_all(0)
            self.dialog.vbox.pack_start(self.selector)

            self.home = gtk.Label("Heimat: %s, %s" % (parent.default_city, parent.default_station))
            self.dialog.vbox.pack_start(self.home, False)

            while True:
                self.dialog.show_all()
                response = self.dialog.run()
                if response == gtk.RESPONSE_ACCEPT:
                    favourites = []
                    model = self.selector.get_model(0)
                    i = model.get_iter_root()
                    while i:
                        favourites.append(model.get_value(i, 0))
                        i = model.iter_next(i)
                    parent.gconf.set_list(parent.GCONF_PATH + 'favourites',
                                          gconf.VALUE_STRING,
                                          favourites
                                         )
                    hildon.hildon_banner_show_information(parent.win, "", "Favoriten gespeichert.")

                elif response == 257:
                    model = self.selector.get_model(0)
                    for item in [gtk.TreeRowReference(model, path)
                                    for path in self.selector.get_selected_rows(0)]:
                        model.remove(model.get_iter(item.get_path()))

                elif response == 258:
                    selected = self.selector.get_selected_rows(0)
                    if len(selected) == 0:
                        hildon.hildon_banner_show_information(self.dialog, "", "Keine Haltestelle ausgewählt!")
                    elif len(selected) > 1:
                        hildon.hildon_banner_show_information(self.dialog, "", "Kann nur eine Haltestelle als Heimat setzen!")
                    else:
                        model = self.selector.get_model(0)
                        station = model.get_value(model.get_iter(selected[0]), 1)

                        parent.gconf.set_string(parent.GCONF_PATH + 'default_city', station.city)
                        parent.default_city = station.city

                        parent.gconf.set_string(parent.GCONF_PATH + 'default_station', station.station)
                        parent.default_station = station.station

                        parent.update_placeholders()

                        self.home.set_text("Heimat: %s, %s" % (parent.default_city, parent.default_station))

                        self.selector.unselect_all(0)
                        hildon.hildon_banner_show_information(self.dialog, "", "Haltestelle als Heimat gespeichert.")

                if response < 257:
                    self.dialog.hide()
                    self.dialog.destroy()
                    break

        def new_favourite(self, widget, station, city):
            if len(station.get_text()) > 0:
                if len(city.get_text()) > 0:
                    obj = backend.Station(station.get_text(), city.get_text())
                else:
                    obj = backend.Station(station.get_text(), self.parent.default_city)
                self.selector.get_model(0).append([str(obj), obj])
                station.set_text("")
                city.set_text("")

    def switch_deparr(self, widget):
        tmp = (self.origin_station.get_text(), self.origin_city.get_text())
        self.origin_station.set_text(self.destination_station.get_text())
        self.origin_city.set_text(self.destination_city.get_text())
        self.destination_station.set_text(tmp[0])
        self.destination_city.set_text(tmp[1])

    def now_toggled(self, widget):
        active = widget.get_active()
        self.date.set_sensitive(not active)
        self.time.set_sensitive(not active)
        if not active:
            now = datetime.datetime.now()
            self.date.set_date(now.year, now.month, now.day)
            self.time.set_time(now.hour, now.minute)

class ResultView:
    def __init__(self, req):
        self.req = req
        self.program = hildon.Program.get_instance()
        self.win = hildon.StackableWindow()
        self.win.set_title("BSAG Fahrten")

        self.box = gtk.VBox()
        self.pan = hildon.PannableArea()
        self.listmodel = gtk.ListStore(str, str, str, str, int)

        self.listview = hildon.GtkTreeView(gtk.HILDON_UI_MODE_NORMAL)
        self.listview.set_model(self.listmodel)
        self.listview.set_grid_lines(gtk.TREE_VIEW_GRID_LINES_HORIZONTAL)
        self.listview.set_headers_visible(True)
        self.listview.connect("row-activated", self.activated)

        renderer = gtk.CellRendererText()

        self.deptime_column = gtk.TreeViewColumn("Abfahrt")
        self.deptime_column.pack_start(renderer, True)
        self.deptime_column.add_attribute(renderer, "text", 0)
        self.listview.append_column(self.deptime_column)

        self.lines_column = gtk.TreeViewColumn("mit den Linien")
        self.lines_column.pack_start(renderer, True)
        self.lines_column.add_attribute(renderer, "text", 1)
        self.lines_column.set_expand(True)
        self.listview.append_column(self.lines_column)

        self.arrtime_column = gtk.TreeViewColumn("Ankunft")
        self.arrtime_column.pack_start(renderer, True)
        self.arrtime_column.add_attribute(renderer, "text", 2)
        self.listview.append_column(self.arrtime_column)

        self.duration_column = gtk.TreeViewColumn("Dauer")
        self.duration_column.pack_start(renderer, True)
        self.duration_column.add_attribute(renderer, "text", 3)
        self.listview.append_column(self.duration_column)

        self.pan.add_with_viewport(self.listview)

        url_button = hildon.Button(gtk.HILDON_SIZE_AUTO_HEIGHT,
            hildon.BUTTON_ARRANGEMENT_VERTICAL,
            title = "Im Browser öffnen")
        url_button.connect("clicked", self.browser)
        self.box.pack_end(url_button, False)

        if hasattr(self.req, "earlier") or hasattr(self.req, "later"):
            hbox = gtk.HBox()
            if hasattr(self.req, "earlier"):
                earlier_button = hildon.Button(gtk.HILDON_SIZE_FINGER_HEIGHT,
                    hildon.BUTTON_ARRANGEMENT_VERTICAL,
                    title = "Früher")
                earlier_button.connect("clicked", self.alter_req, self.req.earlier)
                hbox.pack_start(earlier_button, True)


            if hasattr(self.req, "later"):
                later_button = hildon.Button(gtk.HILDON_SIZE_FINGER_HEIGHT,
                    hildon.BUTTON_ARRANGEMENT_VERTICAL,
                    title = "Später")
                later_button.connect("clicked", self.alter_req, self.req.later)
                hbox.pack_end(later_button, True)

            self.box.pack_end(hbox, False)

        self.box.pack_start(self.pan)


        self.rebuild_model()

        self.win.add(self.box)
        self.win.show_all()

    def rebuild_model(self):
        self.listmodel.clear()
        i = 0
        for route in self.req.routes:
            self.listmodel.append([
                route.origin()[1].strftime("%H:%M"),
                ", ".join([s["line_type"]+' '+s["line"] for s in route]),
                route.destination()[1].strftime("%H:%M"),
                '%d:%02d' % (route.duration().seconds/3600, (route.duration().seconds%3600)/60),
                i
            ])
            i += 1
        hildon.hildon_gtk_window_set_progress_indicator(self.win, 0)

    def alter_req(self, button, func):
        if button:
            thread = Thread(target=self.alter_req, args=(None, func))
            thread.start()
            hildon.hildon_gtk_window_set_progress_indicator(self.win, 1)
        else:
            self.req = func()
            gobject.idle_add(self.rebuild_model, priority=gobject.PRIORITY_DEFAULT)

    def activated(self, view, path, col):
        RouteView(self.req.routes[path[0]])

    def browser(self, button):
        bus = dbus.SessionBus()
        proxy_obj = bus.get_object('com.nokia.osso_browser', '/com/nokia/osso_browser/request')
        dbus_iface = dbus.Interface(proxy_obj, 'com.nokia.osso_browser')
        dbus_iface.load_url(self.req.get_url())

class RouteView:
    def __init__(self, route):
        self.program = hildon.Program.get_instance()
        self.win = hildon.StackableWindow()
        self.win.set_title("BSAG Fahrt")

        self.pan = hildon.PannableArea()
        self.box = gtk.VBox()
        ROWS_PER_SECTION = 3
        self.table = gtk.Table(3, len(route)*ROWS_PER_SECTION)

        i = 0
        for section in route:
            self.tab_add("ab "+section["origin_time"].strftime("%H:%M"), 0, i)
            self.tab_add(section["origin_station"], 1, i)
            self.tab_add(section["line_type"]+' '+section['line'], 2, i)

            self.tab_add("an "+section["destination_time"].strftime("%H:%M"), 0, i+1)
            self.tab_add(section["destination_station"], 1, i+1)
            if section.get('delay'):
                self.tab_add("%d Min. verspätet" % section['delay'], 2, i+1)
            self.table.attach(gtk.HSeparator(), 0, 3, i+2, i+3)

            i += ROWS_PER_SECTION

        self.box.pack_start(self.table, False)
        self.pan.add_with_viewport(self.box)
        self.win.add(self.pan)
        self.win.show_all()

    def tab_add(self, s, x, y):
        self.table.attach(gtk.Label(s), x, x+1, y, y+1)


def main():
    # for some reason, conic.Connection has to be created before the MainLoop starts!
    gui = SearchForm(conic.Connection())
    gtk.main()

if __name__ == "__main__":
    main()
