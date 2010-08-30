#!/usr/bin/python
def main():
	import urllib, httplib, datetime, sys, re
	from BeautifulSoup import BeautifulSoup
	timenow = datetime.datetime.now().timetuple()
	formparam = {"language":"de", "sessionID":"0", "place_origin":"Bremen", "place_destination":"Bremen", \
				"type_origin":"stop", "type_destination":"stop", "nameState_origin":"empty", \
				"nameState_destination":"empty", \
				"itdTripDateTimeDepArr":"dep", "itdDateYear":timenow[0], \
				"itdDateMonth":timenow[1],"itdDateDay":timenow[2], "itdTimeHour":timenow[3], \
				"itdTimeMinute":timenow[4]}
	if len(sys.argv) == 1:
		print """Program usage:
	bsag.py Starthaltestelle [Zielhaltestelle]

	Starthaltestelle: self-explaining
	Zielhaltestelle: self-explaining, optional. Default ist Hbf
	"""
		sys.exit()
	elif len(sys.argv) == 2:
		formparam["name_origin"] = sys.argv[1]
		formparam["name_destination"] = "Hauptbahnhof"
	elif len(sys.argv) == 3:
		formparam["name_origin"] = sys.argv[1]
		formparam["name_destination"] = sys.argv[2]

	params = urllib.urlencode(formparam)
	headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "text/plain"}

	conn = httplib.HTTPConnection("62.206.133.180:80")
	conn.request("POST", "/bsag/XSLT_TRIP_REQUEST2?language=de&itdLPxx_transpCompany=bsag&", params, headers)
	response = conn.getresponse()
	if response.reason != "OK":
		sys.exit("Host unreachable!")
	data = response.read()
	conn.close()

	soup = BeautifulSoup(data)
	message = soup.findAll("tr", attrs={"class": "Message"})
	if len(message) > 0:
		for msg in message[0].findAll(attrs={"class":"Messagetext"}):
			print (msg.string+"\n").encode("utf-8")
			if re.match("Start", msg.string):
				alternative = soup.find("select", attrs={"name": re.compile("name_origin")})
				if not alternative:
					sys.exit(u"Keine Verbindung gefunden".encode("utf-8"))
				alternatives = alternative.findAll("option")
				for alt in alternatives:
					print alt.string
				print "Bitte Haltestelle genauer spezifizieren\n"
			elif re.match("Ziel", msg.string):
				alternative = soup.find("select", attrs={"name": re.compile("name_destination")})
				if not alternative:
					sys.exit(u"Keine Verbindung gefunden".encode("utf-8"))
				alternatives = alternative.findAll("option")
				for alt in alternatives:
					print alt.string
				print "Bitte Haltestelle genauer spezifizieren"
		sys.exit()
	firstRoute = soup.findAll(attrs={'name': 'Trip1'})[0].parent.parent.parent

	trs = firstRoute.findAll(lambda tag: tag.name == 'tr')
	for tr in trs:
		station = []
		for span in tr.findAll('span', attrs={'class': re.compile("^labelText")}):
			if not span.contents:
				continue
			else:
				station.append(span.contents[0])
		if len(station) == 0: 
			continue
		try:
			print u"\t".join(station).encode("utf-8")
		except TypeError:
			print ""
	# print firstRoute.prettify()
if __name__ == "__main__":
	main()
