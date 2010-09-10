#!/usr/bin/python
# -*- coding: utf-8 -*-

from datetime import datetime, time, timedelta
import urllib
import re
import sys
from BeautifulSoup import BeautifulSoup

_REQ_URL = "http://62.206.133.180/bsag/XSLT_TRIP_REQUEST2?language=de&itdLPxx_transpCompany=bsag"

class AmbiguityException(Exception):
    def __init__(self, field, options = []):
        self.field = field
        self.options = [unicode(op) for op in options]

    def __str__(self):
        return unicode(self).encode('utf-8')

    def __unicode__(self):
        if len(self.options):
            return u"The field '%s' was ambigous, the following options were suggested: %s" % (self.field, u", ".join(self.options))
        else:
            return u"The field '%s' was ambigous" % unicode(self.field)

class Station:
    def __init__(self, station, city = None):
        if (city == None or city == "") and station.find(', ') > -1:
            city = station.split(', ')[0]
            station = station.split(', ')[1]
        self.station = station.replace(' (Main Station)', '')
        self.city = city

    def __str__(self):
        return unicode(self).encode('utf-8')

    def __unicode__(self):
        if self.city and self.city != "":
            return u"%s, %s" % (self.city, self.station)
        else:
            return self.station

    def __repr__(self):
        return 'Station(%s, %s)' % (repr(self.station), repr(self.city))

class Route:
    """
    A complete route from one station to another, possibly
    containing multiple sections.
    """
    def __init__(self):
        self.sections = []

    def __unicode__(self):
        if len(self.sections) == 0:
            return "Unknown route"
        start = self.sections[0]['origin_station']
        goal = self.sections[-1]['destination_station']
        return "Route from %s to %s using %s" % (start, goal, ', '.join([section['line_type']+' '+section['line'] for section in self.sections]))

    def __str__(self):
        return unicode(self).encode('utf-8')

    def duration(self):
        return self.sections[-1]['destination_time'] - self.sections[0]['origin_time']

    def origin(self):
        return (self.sections[0]['origin_station'], self.sections[0]['origin_time'])

    def destination(self):
        return (self.sections[-1]['destination_station'], self.sections[-1]['destination_time'])

    def add_section(self, section):
        self.sections.append(section)

class Request:
    def __init__(self, origin, destination, date, deparr = 'dep'):
        self.origin = origin
        self.destination = destination
        self.date = date
        self.deparr = deparr

        post = urllib.urlencode({
            'language': 'de',
            'sessionID': '0',
            'useRealtime': '0',
            'place_origin': self.origin.city,
            'name_origin': self.origin.station,
            'place_destination': self.destination.city,
            'name_destination': self.destination.station,
            'type_origin': 'stop',
            'type_destination': 'stop',
            'nameState_origin': 'empty',
            'nameState_destination': 'empty',
            'itdTripDateTimeDepArr': deparr,
            'itdTimeHour': date.hour,
            'itdTimeMinute': date.minute,
            'itddateDay': date.day,
            'itddateMonth': date.month,
            'itddateYear': date.year,
            'simple': 'Suche starten'
        })

        ret = urllib.urlopen(_REQ_URL, post)
        self.html = ret.read()
        self.soup = BeautifulSoup(self.html.replace('\xa0', ' '))
        try:
            self.table = self.soup.find(attrs={'name': 'Trip1'}).parent.parent.parent
        except AttributeError:
            errmsg = self.soup.findAll('span', attrs={'class': 'errorTextBold'})
            for msg in errmsg:
                if len(msg) == len(msg('img')):
                    continue
                select = msg.parent.parent.parent.find('select', size=lambda s: s > 1)
                name_translation = {
                    'name_origin': 'origin_station',
                    'place_origin': 'origin_station',
                    'name_destination': 'destination_station',
                    'place_destination': 'destination_city',
                }
                field = name_translation[select['name']]
                options = [option.string.strip() for option in select.findAll('option')]
                raise AmbiguityException(field, options)
            else:
                raise

        self.routes = []
        route = Route()
        section = {}

        for tr in self.table('tr'):
            tds = tr('td')

            try:
                if tds[0].has_key('class') and tds[0]['class'] == 'kaestchen':
                    if len(route.sections) > 0:
                        self.routes.append(route)
                        route = Route()
                elif tds[3].span.string == u'ab ':
                    # start of (new) route section
                    origin_time = datetime.combine(
                        self.date.date(),
                        datetime.strptime(tds[1].span.string, '%H:%M').time()
                    )
                    if self.date - origin_time > timedelta(0, 0, 0, 0, 30):
                        origin_time += timedelta(1)
                    section = {
                        'origin_station': Station(tds[4].span.string),
                        'origin_time': origin_time,
                        'line': tds[7].span.string.split(' ')[1],
                        'line_type': tds[7].span.string.split(' ')[0],
                    }
                elif tds[3].span.string == u'an ':
                    # destination of route section
                    destination_time = datetime.combine(
                        self.date.date(),
                        datetime.strptime(tds[1].span.string, '%H:%M').time()
                    )
                    if destination_time < origin_time:
                        destination_time += timedelta(1)
                    section['destination_station'] = Station(tds[4].span.string)
                    section['destination_time'] = destination_time
                    route.add_section(section)
                    section = {}
            except IndexError:
                pass

if __name__ == '__main__':
    if len(sys.argv) == 1:
        print """Program usage:
    %s Starthaltestelle [Zielhaltestelle]

    Starthaltestelle: self-explaining
    Zielhaltestelle: self-explaining, optional. Default ist Hbf
    """ % sys.argv[0]
        sys.exit()
    else:
        origin = Station(sys.argv[1], 'Bremen' if sys.argv[1].find(', ') == -1 else None)
        if len(sys.argv) == 2:
            destination = Station("Hauptbahnhof", "Bremen")
        elif len(sys.argv) == 3:
            destination = Station(sys.argv[2], "Bremen" if sys.argv[2].find(', ') == -1 else None)
    r = Request(origin, destination, datetime.now())
    i = 1
    for route in r.routes:
        print '%d. Fahrt, Dauer %s' % (i, route.duration())
        for section in route.sections:
            print u'  %s\tab\t%-40s\t%s %s' % (section['origin_time'].strftime('%H:%M'), unicode(section['origin_station']), section['line_type'], section['line'])
            print u'  %s\tan\t%-40s' % (section['destination_time'].strftime('%H:%M'), unicode(section['destination_station']))
        i += 1
