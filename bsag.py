#!/usr/bin/python
# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
import urllib
import re
import sys
from lxml import html

_REQ_URL = "http://62.206.133.180/bsag/XSLT_TRIP_REQUEST2?language=de&itdLPxx_transpCompany=bsag"

def find_attrs(etree, tag, attrs):
    elements = etree.iterfind('.//'+tag)
    matches = []
    for element in elements:
        for (key, value) in attrs.iteritems():
            if callable(value):
                if not value(element.get(key)):
                    break
            elif element.get(key) != value:
                break
        else:
            matches.append(element)
    return matches

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

class Route(list):
    """
    A complete route from one station to another, possibly
    containing multiple sections.
    """
    def __unicode__(self):
        if len(self.sections) == 0:
            return "Unknown route"
        start = self.origin()[0]
        goal = self.destionation()[0]
        return "Route from %s to %s using %s" % (start, goal, ', '.join([section['line_type']+' '+section['line'] for section in self]))

    def __str__(self):
        return unicode(self).encode('utf-8')

    def duration(self):
        return self[-1]['destination_time'] - self[0]['origin_time']

    def origin(self):
        return (self[0]['origin_station'], self[0]['origin_time'])

    def destination(self):
        return (self[-1]['destination_station'], self[-1]['destination_time'])

class Request:
    def __init__(self, **kwargs):
        if kwargs.has_key('origin') and kwargs.has_key('destination'):
            origin = kwargs['origin']
            destination = kwargs['destination']
            self.date = kwargs.get('date', datetime.now())
            deparr = kwargs.get('deparr', 'dep')

            self.post = {
                'language': 'de',
                'sessionID': '0',
                'useRealtime': '1',
                'place_origin': origin.city,
                'name_origin': origin.station,
                'place_destination': destination.city,
                'name_destination': destination.station,
                'type_origin': 'stop',
                'type_destination': 'stop',
                'nameState_origin': 'empty',
                'nameState_destination': 'empty',
                'itdTripDateTimeDepArr': deparr,
                'itdTimeHour': self.date.hour,
                'itdTimeMinute': self.date.minute,
                'itddateDay': self.date.day,
                'itddateMonth': self.date.month,
                'itddateYear': self.date.year,
                'simple': 'Suche starten'
            }
        elif kwargs.has_key('post'):
            # do we need separate URLs? I doubt it...
            self.post = kwargs['post']
            self.date = kwargs.get('date', datetime.now())
        else:
            raise TypeError('either "origin" and "destination" or "post" have to be provided')

        ret = urllib.urlopen(_REQ_URL, urllib.urlencode(self.post))
        # unneccessary outside of HTML and confuses 'if's
        self.html = ret.read().replace('\xa0', ' ')
        self.xml = html.fromstring(self.html)
        try:
            self.table = find_attrs(self.xml, 'a', {'name': 'Trip1'})[0].getparent().getparent().getparent()
        except IndexError:
            errmsg = find_attrs(self.xml, 'span', {'class': 'errorTextBold'})
            for msg in errmsg:
                if not msg.text:
                    continue
                try:
                    select = find_attrs(msg.getparent().getparent().getparent(), 'select', {'size': lambda s: s > 1})[0]
                    name_translation = {
                        'name_origin': 'origin_station',
                        'place_origin': 'origin_station',
                        'name_destination': 'destination_station',
                        'place_destination': 'destination_city',
                    }
                    field = name_translation[select.get('name')]
                    options = [option.text.strip() for option in select.findall('option')]
                    raise AmbiguityException(field, options)
                except:
                    raise Exception(msg.text)
            else:
                raise

        self.routes = []
        route = Route()
        section = {}

        for tr in self.table.findall('tr'):
            tds = tr.findall('td')

            try:
                if tds[0].get('class') == 'kaestchen':
                    if len(route) > 0:
                        self.routes.append(route)
                        route = Route()
                elif tds[3].find('span').text == u'ab ':
                    # start of (new) route section
                    origin_time = datetime.combine(
                        self.date.date(),
                        datetime.strptime(tds[1].find('span').text, '%H:%M').time()
                    )
                    if self.date - origin_time > timedelta(0, 0, 0, 0, 30):
                        origin_time += timedelta(1)
                    try:
                        delay = tds[8].find('.//span').find('span').text
                        delay = int(delay[0:delay.find(' ')])
                    except (AttributeError, ValueError):
                        delay = 0
                    section = {
                        'origin_station': Station(tds[4].find('span').text),
                        'origin_time': origin_time,
                        'line': tds[7].find('span').text.split(' ')[1],
                        'line_type': tds[7].find('span').text.split(' ')[0],
                        'delay': delay,
                    }
                elif tds[3].find('span').text == u'an ':
                    # destination of route section
                    destination_time = datetime.combine(
                        self.date.date(),
                        datetime.strptime(tds[1].find('span').text, '%H:%M').time()
                    )
                    if destination_time < origin_time:
                        destination_time += timedelta(1)
                    section['destination_station'] = Station(tds[4].find('span').text)
                    section['destination_time'] = destination_time
                    route.append(section)
                    section = {}
            except (IndexError, AttributeError):
                pass

    def create_post(self):
        post = {}
        for option in find_attrs(self.xml, 'input', {"name": lambda nam: nam and len(nam) > 0, "value": lambda val: val and len(val) > 0}):
            post[option.get("name")] = option.get("value")
        post["itdLPxx_view"] = ""
        post["itdLPxx_ShowFare"] = ""
        post["itdLPxx_view"] = ""
        return post

    def earlier(self):
        post = self.create_post()
        post["command"] = "tripPrev"
        return Request(post=post)

    def later(self):
        post = self.create_post()
        post["command"] = "tripNext"
        return Request(post=post)

    def get_url(self):
        return (_REQ_URL
          + ('&' if _REQ_URL.find('?') > -1 else '?')
          + urllib.urlencode(self.post)
        )

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
    try:
        r = Request(origin=origin, destination=destination, date=datetime.now())
        i = 1
        for route in r.routes:
            print '%d. Fahrt, Dauer %s' % (i, route.duration())
            for section in route:
                print u'  %s\tab\t%-30s\t%s %s' % (section['origin_time'].strftime('%H:%M'), unicode(section['origin_station']), section['line_type'], section['line'])
                if section['delay']:
                    print u'  %s\tan\t%-30s\t%d Minuten verspätet' % (section['destination_time'].strftime('%H:%M'), unicode(section['destination_station']), section['delay'])
                else:
                    print u'  %s\tan\t%-30s' % (section['destination_time'].strftime('%H:%M'), unicode(section['destination_station']))
            i += 1
    except AmbiguityException, e:
        print '%s war nicht eindeutig. Möglichkeiten:' % e.field
        for option in e.options:
            print ' * %s' % option
