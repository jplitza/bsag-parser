#!/usr/bin/python

import gobject
import gtk
import hildon
import datetime
import bsag as backend
from threading import Thread

gobject.threads_init()
gtk.gdk.threads_init()

class SearchForm:
    # TODO: make default configurable
    DEFAULT_CITY = "Bremen"

    def __init__(self):
        self.program = hildon.Program.get_instance()
        self.win = hildon.StackableWindow()
        self.win.set_title("BSAG")
        self.win.connect("destroy", gtk.main_quit, None)

        self.pan = hildon.PannableArea()
        self.form = gtk.VBox()
        table = gtk.Table(2, 4, False)

        self.origin_station = hildon.Entry(
            gtk.HILDON_SIZE_FINGER_HEIGHT)
        self.origin_station.connect("activate", self.search_activated)
        self.origin_station.set_placeholder("Starthaltestelle")
        table.attach(self.origin_station, 0, 1, 0, 1)

        self.origin_city = hildon.Entry(
            gtk.HILDON_SIZE_FINGER_HEIGHT)
        self.origin_city.connect("activate", self.search_activated)
        self.origin_city.set_placeholder("Stadt (Bremen)")
        table.attach(self.origin_city, 1, 2, 0, 1)

        self.destination_station = hildon.Entry(
            gtk.HILDON_SIZE_FINGER_HEIGHT)
        self.destination_station.connect("activate", self.search_activated)
        self.destination_station.set_placeholder("Zielhaltestelle")
        table.attach(self.destination_station, 0, 1, 1, 2)

        self.destination_city = hildon.Entry(
            gtk.HILDON_SIZE_FINGER_HEIGHT)
        self.destination_city.connect("activate", self.search_activated)
        self.destination_city.set_placeholder("Stadt (Bremen)")
        table.attach(self.destination_city, 1, 2, 1, 2)

        self.date = hildon.DateButton(
            gtk.HILDON_SIZE_FINGER_HEIGHT,
            hildon.BUTTON_ARRANGEMENT_VERTICAL)
        table.attach(self.date, 0, 1, 2, 3)

        self.time = hildon.TimeButton(
            gtk.HILDON_SIZE_FINGER_HEIGHT,
            hildon.BUTTON_ARRANGEMENT_VERTICAL)
        table.attach(self.time, 1, 2, 2, 3)

        submit = hildon.Button(gtk.HILDON_SIZE_FINGER_HEIGHT,
            hildon.BUTTON_ARRANGEMENT_VERTICAL,
            title = "Suche starten")
        submit.connect("clicked", self.search_activated)
        table.attach(submit, 0, 2, 3, 4)

        self.form.pack_start(table, False, False, 0)
        self.pan.add_with_viewport(self.form)
        self.win.add(self.pan)

        self.win.show_all()

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
                backend.Station(self.origin_station.get_text(), origin_city),
                backend.Station(self.destination_station.get_text(), destination_city),
                datetime.datetime(date[0], date[1]+1, date[2], time[0], time[1])
            )
        except backend.AmbiguityException, e:
            self.amb = e
        except AttributeError:
            self.errmsg = 'Keine Haltestelle gefunden!'
        finally:
            gobject.idle_add(self.present_results)

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

class ResultView:
    def __init__(self, req):
        self.req = req
        self.program = hildon.Program.get_instance()
        self.win = hildon.StackableWindow()
        self.win.set_title("BSAG Fahrten")

        self.pan = hildon.PannableArea()
        self.listmodel = gtk.ListStore(str, str, str, str, int)

        i = 0
        for route in self.req.routes:
            self.listmodel.append([
                route.origin()[1].strftime("%H:%M"),
                ", ".join([s["line_type"]+' '+s["line"] for s in route.sections]),
                route.destination()[1].strftime("%H:%M"),
                '%d:%02d' % (route.duration().seconds/3600, (route.duration().seconds%3600)/60),
                i
            ])
            i += 1

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
        self.win.add(self.pan)
        self.win.show_all()

    def activated(self, view, path, col):
        RouteView(self.req.routes[path[0]])

class RouteView:
    def __init__(self, route):
        self.program = hildon.Program.get_instance()
        self.win = hildon.StackableWindow()
        self.win.set_title("BSAG Fahrt")

        self.pan = hildon.PannableArea()
        self.box = gtk.VBox()
        ROWS_PER_SECTION = 3
        self.table = gtk.Table(3, len(route.sections)*ROWS_PER_SECTION)

        i = 0
        for section in route.sections:
            self.tab_add("ab "+section["origin_time"].strftime("%H:%M"), 0, i)
            self.tab_add(unicode(section["origin_station"]), 1, i)
            self.tab_add(section["line_type"]+' '+section['line'], 2, i)

            self.tab_add("an "+section["destination_time"].strftime("%H:%M"), 0, i+1)
            self.tab_add(section["destination_station"], 1, i+1)
            self.table.attach(gtk.HSeparator(), 0, 3, i+2, i+3)

            i += ROWS_PER_SECTION

        self.box.pack_start(self.table, False)
        self.pan.add_with_viewport(self.box)
        self.win.add(self.pan)
        self.win.show_all()

    def tab_add(self, s, x, y):
        self.table.attach(gtk.Label(s), x, x+1, y, y+1)


def main():
    gui = SearchForm()
    #req = backend.Request(backend.Station("West"), backend.Station("Hbf"), datetime.datetime.now())
    #gui = ResultView(req)
    gtk.main()

if __name__ == "__main__":
    main()
