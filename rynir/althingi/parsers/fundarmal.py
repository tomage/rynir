import re
from htmlparser import ScraperParserHTML
from metaparser import RegisterScraperParser
from althingi.models import *
from fundur import url_to_lth_fnr


SATUHJA_RE = re.compile('\(([^\)]+)\) greiddu ekki')
FJARSTADDIR_RE = re.compile('\(([^\)]+)\) fjarstaddir')
UMRAEDA_ID_RE = re.compile('/altext/(\d+/\d+/l\d+)\.sgml')
DAGSTIMI_RE = re.compile('(\d\d\d\d-\d\d-\d\d? \d\d:\d\d):')


class ScraperParserFundarmal(ScraperParserHTML):
  MATCH_URLS = ('http://www.althingi.is/altext/\d+/\d+/l\d+\.sgml$', )
  SCRAPE_URLS = ( )

  def parse(self, url, data, fromEncoding=None):
    soup = ScraperParserHTML.parse(self, url, data,
                                  fromEncoding=(fromEncoding or 'windows-1252'))
    efni = soup.h2
    dt = DAGSTIMI_RE.search(soup.title.string)
    dagstimi = dt.group(1)

    lth, fnr = None, None
    for a in soup.fetch('a'):
      l, f = url_to_lth_fnr(a.get('href', ''))
      if l and f:
        lth, fnr = l, f
        break

    for para in soup.fetch('p'):
      brtt = para.a
      vote = para.dl
      if brtt is None and vote:
        elem = vote.next
        svar = None
        ja, nei, fj, sh = [], [], [], []
        while elem:
          name = getattr(elem, 'name', None)

          if name == 'dt':
            svar = elem.b.string.replace('&nbsp;', '').strip()[:-1]

          elif name == 'dd':
            folk = elem.string.replace('.', '').strip().split(', ')
            if svar.startswith('j'):
              ja = folk
            elif svar.startswith('n'):
              nei = folk

          elif name == 'p':
            satuhja = SATUHJA_RE.search(elem.string or '')
            fjarstaddir = FJARSTADDIR_RE.search(elem.string or '')
            if satuhja:
              sh = satuhja.group(1).replace('.', '').strip().split(', ')
            elif fjarstaddir:
              fj = fjarstaddir.group(1).replace('.', '').strip().split(', ')

            if not (elem.string and elem.string.strip()): break

          elem = elem.next

        # FIXME: Create Umraeda/Kosning/Atkvaedi objects in DB
        uid = UMRAEDA_ID_RE.search(url).group(1)
        updating = Umraeda.objects.filter(uid=uid)
        if updating:
          for u in updating:
            u.delete()

        print 'Umraeda: %s / %s / %s' % (fnr, lth, uid)
        print 'J: %s' % ja
        print 'N: %s' % nei
        print 'F: %s' % fj
        print 'S: %s' % sh

        nu = Umraeda(uid=uid,
                     fundur=Fundur.objects.filter(fnr=fnr, lth=lth)[0],
                     timi=dagstimi,
                     efni=efni,
                     #url_ferill=,
                     titill=soup.h2.string)
        nu.save()

        nk = Kosning(umraeda=nu,
                     titill=soup.h2.string,
                     timi=dagstimi, # FIXME: wrong?
                     url_skjal='')
        nk.save()

        for svar, folk in (('J', ja), ('N', nei), ('F', fj), ('S', sh)):
          for stafir in folk:
            try:
              Atkvaedi(kosning=nk,
                       thingmadur=Thingmadur.objects.filter(stafir=stafir)[0],
                       atkvaedi=svar).save()
            except IndexError:
              print 'Othekkur thingmadur: %s (%s)' % (stafir, svar)

    return True

RegisterScraperParser(ScraperParserFundarmal)
