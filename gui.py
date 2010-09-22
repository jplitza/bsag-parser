#!/usr/bin/python
# -*- coding: utf-8 -*-

import datetime
from threading import Thread
import gobject
import dbus
import gtk
import hildon
import conic
import bsag as backend

gobject.threads_init()
gtk.gdk.threads_init()

class SearchForm:
    DEFAULT_CITY = "Bremen"
    FAVOURITES = [
        backend.Station('Westerstraße', 'Bremen'),
        backend.Station('Brüsseler Straße', 'Bremen'),
        backend.Station('Hauptbahnhof', 'Bremen'),
        backend.Station('Universität Zentralbereich', 'Bremen'),
    ]

    def __init__(self, conic = None):
        self.conic = conic
        # TODO: do this nice
        favicon = "/usr/share/icons/hicolor/48x48/hildon/general_mybookmarks_folder.png"
        self.program = hildon.Program.get_instance()
        self.win = hildon.StackableWindow()
        self.win.set_title("BSAG")
        self.win.connect("destroy", gtk.main_quit)

        self.pan = hildon.PannableArea()
        self.form = gtk.VBox()
        table = gtk.Table(3, 4, False)


        self.origin_station = hildon.Entry(
            gtk.HILDON_SIZE_FINGER_HEIGHT)
        self.origin_station.connect("activate", self.search_activated)
        self.origin_station.connect("changed", self.lock_submit)
        self.origin_station.set_placeholder("Starthaltestelle")
        table.attach(self.origin_station, 1, 2, 0, 1)

        self.origin_city = hildon.Entry(
            gtk.HILDON_SIZE_FINGER_HEIGHT)
        self.origin_city.connect("activate", self.search_activated)
        self.origin_city.set_placeholder("Stadt (Bremen)")
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
        self.destination_station.connect("changed", self.lock_submit)
        self.destination_station.set_placeholder("Zielhaltestelle")
        table.attach(self.destination_station, 1, 2, 1, 2)

        self.destination_city = hildon.Entry(
            gtk.HILDON_SIZE_FINGER_HEIGHT)
        self.destination_city.connect("activate", self.search_activated)
        self.destination_city.set_placeholder("Stadt (Bremen)")
        table.attach(self.destination_city, 2, 3, 1, 2)

        arrfav = hildon.Button(gtk.HILDON_SIZE_FINGER_HEIGHT,
            hildon.BUTTON_ARRANGEMENT_VERTICAL,
            title = "")
        arrfav.set_image(gtk.image_new_from_file(favicon))
        arrfav.connect("clicked", self.favourite_selector, (self.destination_station, self.destination_city))
        table.attach(arrfav, 0, 1, 1, 2, gtk.FILL, gtk.FILL)

        self.deparr = hildon.PickerButton(
            gtk.HILDON_SIZE_FINGER_HEIGHT,
            hildon.BUTTON_ARRANGEMENT_VERTICAL)
        deparr_selector = hildon.TouchSelector()
        deparr_model = gtk.ListStore(str, str)
        deparr_model.append(["ab", "dep"])
        deparr_model.append(["an", "arr"])
        deparr_selector.append_text_column(deparr_model, True)
        self.deparr.set_selector(deparr_selector)
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

        self.submit = hildon.Button(gtk.HILDON_SIZE_FINGER_HEIGHT,
            hildon.BUTTON_ARRANGEMENT_VERTICAL,
            title = "Suche starten")
        self.submit.connect("clicked", self.search_activated)
        table.attach(self.submit, 0, 3, 3, 4)
        self.lock_submit(None)

        self.form.pack_start(table, False, False, 0)
        self.pan.add_with_viewport(self.form)
        self.win.add(self.pan)

        self.win.show_all()

    def lock_submit(self, widget):
        self.submit.set_sensitive(
            self.origin_station.get_text() != "" and self.destination_station.get_text() != ""
        )

    def search_activated(self, widget = None):
        thread = Thread(target=self.do_search)
        thread.start()
        hildon.hildon_gtk_window_set_progress_indicator(self.win, 1)

    def do_search(self):
        try:
            date = self.date.get_date()
            time = self.time.get_time()
            origin_city = self.origin_city.get_text()
            if origin_city == "":
                origin_city = self.DEFAULT_CITY
            destination_city = self.destination_city.get_text()
            if destination_city == "":
                destination_city = self.DEFAULT_CITY
            self.request = backend.Request(
                origin=backend.Station(self.origin_station.get_text(), origin_city),
                destination=backend.Station(self.destination_station.get_text(), destination_city),
                date=datetime.datetime(date[0], date[1]+1, date[2], time[0], time[1]),
                deparr="dep" if self.deparr.get_active() == 0 else "arr"
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
        selector = hildon.TouchSelector()
        model = gtk.ListStore(str)
        for item in l:
            model.append([item])

        selector.append_text_column(model, True)
        return selector

    def present_results(self):
        hildon.hildon_gtk_window_set_progress_indicator(self.win, 0)
        if hasattr(self, "request"):
            self.resultview = ResultView(self.request)
            del self.request
        elif hasattr(self, "amb"):
            if hasattr(self, self.amb.field):
                self.picker_dialog = hildon.PickerDialog(self.win)
                selector = self.selector_from_list(self.amb.options)
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
        selector = self.selector_from_list(self.FAVOURITES)
        self.favourite_dialog.set_selector(selector)
        selector.connect("changed", self.select_favourite, target)
        self.favourite_dialog.set_title("Favorit auswählen")
        self.favourite_dialog.show_all()

    def select_favourite(self, widget, data, field):
        field[0].set_text(self.FAVOURITES[widget.get_active(0)].station)
        field[1].set_text(self.FAVOURITES[widget.get_active(0)].city)
        self.favourite_dialog.destroy()
        del self.favourite_dialog

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
