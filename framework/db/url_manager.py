#!/usr/bin/env python
'''
owtf is an OWASP+PTES-focused try to unite great tools and facilitate pen testing
Copyright (c) 2011, Abraham Aranguren <name.surname@gmail.com> Twitter: @7a_ http://7-a.org
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
    * Redistributions of source code must retain the above copyright
      notice, this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright
      notice, this list of conditions and the following disclaimer in the
      documentation and/or other materials provided with the distribution.
    * Neither the name of the copyright owner nor the
      names of its contributors may be used to endorse or promote products
      derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

The DB stores HTTP transactions, unique URLs and more.
'''
from framework.dependency_management.dependency_resolver import BaseComponent
from framework.lib.general import *
from framework.db import models
import re
import logging


class URLManager(BaseComponent):
    NumURLsBefore = 0

    COMPONENT_NAME = "url_manager"

    def __init__(self, Core):
        self.register_in_service_locator()
        self.Core = Core
        self.config = self.get_component("config")
        self.target = self.get_component("target")
        # Compile regular expressions once at the beginning for speed purposes:
        self.IsFileRegexp = re.compile(self.config.FrameworkConfigGet('REGEXP_FILE_URL'), re.IGNORECASE)
        self.IsSmallFileRegexp = re.compile(self.config.FrameworkConfigGet('REGEXP_SMALL_FILE_URL'), re.IGNORECASE)
        self.IsImageRegexp = re.compile(self.config.FrameworkConfigGet('REGEXP_IMAGE_URL'), re.IGNORECASE)
        self.IsURLRegexp = re.compile(self.config.FrameworkConfigGet('REGEXP_VALID_URL'), re.IGNORECASE)
        self.IsSSIRegexp = re.compile(self.config.FrameworkConfigGet('REGEXP_SSI_URL'), re.IGNORECASE)

    def IsRegexpURL(self, URL, Regexp):
        if len(Regexp.findall(URL)) > 0:
            return True
        return False

    def IsSmallFileURL(self, URL):
        return self.IsRegexpURL(URL, self.IsSmallFileRegexp)

    def IsFileURL(self, URL):
        return self.IsRegexpURL(URL, self.IsFileRegexp)

    def IsImageURL(self, URL):
        return self.IsRegexpURL(URL, self.IsImageRegexp)

    def IsSSIURL(self, URL):
        return self.IsRegexpURL(URL, self.IsSSIRegexp)

    def GetURLsToVisit(self, target=None):
        Session = self.target.GetUrlDBSession(target)
        session = Session()
        urls = session.query(models.Url.url).filter_by(visited=False).all()
        session.close()
        urls = [i[0] for i in urls]
        return (urls)

    def IsURL(self, URL):
        return self.IsRegexpURL(URL, self.IsURLRegexp)

    def GetNumURLs(self):
        # return self.Core.DB.GetLength(DBPrefix+'ALL_URLS_DB')
        Session = self.target.GetUrlDBSession()
        session = Session()
        count = session.query(models.Url).count()
        session.close()
        return (count)

    def AddURLToDB(self, url, visited, found=None, target=None):
        Message = ''
        if self.IsURL(url):  # New URL
            url = url.strip()  # Make sure URL is clean prior to saving in DB, nasty bugs can happen without this
            scope = self.target.IsInScopeURL(url)
            Session = self.target.GetUrlDBSession()
            session = Session()
            session.merge(models.Url(url=url, visited=visited, scope=scope))
            session.commit()
            session.close()
        return Message

    def AddURL(self, url, found=None, target=None):  # Adds a URL to the relevant DBs if not already added
        visited = False
        if found != None:  # Visited URL -> Found in [ True, False ]
            visited = True
        return self.AddURLToDB(url, visited, found=found, target=target)

    def AddURLsStart(self):
        self.NumURLsBefore = self.GetNumURLs()

    def AddURLsEnd(self):
        NumURLsAfter = self.GetNumURLs()
        Message = str(NumURLsAfter - self.NumURLsBefore) + " URLs have been added and classified"
        logging.info(Message)
        return (NumURLsAfter - self.NumURLsBefore)  # Message

    def ImportProcessedURLs(self, urls_list, target_id=None):
        Session = self.target.GetUrlDBSession(target_id)
        session = Session()
        for url, visited, scope in urls_list:
            session.merge(models.Url(url=url, visited=visited, scope=scope))
            logging.info("Added " + url + " to URLs DB")
        session.commit()
        session.close()

    def ImportURLs(self, url_list,
                   target=None):  # Extracts and classifies all URLs passed. Expects a newline separated URL list
        imported_urls = []
        self.AddURLsStart()
        Session = self.target.GetUrlDBSession(target)
        session = Session()
        for url in url_list:
            if self.IsURL(url):
                imported_urls.append(url)
                session.merge(models.Url(url=url))
        session.commit()
        session.close()
        count = self.AddURLsEnd()
        Message = str(count) + " URLs have been added and classified"
        return (imported_urls)  # Return imported urls

    # -------------------------------------------------- API Methods --------------------------------------------------
    def DeriveUrlDict(self, url_obj):
        udict = dict(url_obj.__dict__)
        udict.pop("_sa_instance_state")
        return udict

    def DeriveUrlDicts(self, url_obj_list):
        dict_list = []
        for url_obj in url_obj_list:
            dict_list.append(self.DeriveUrlDict(url_obj))
        return dict_list

    def GenerateQueryUsingSession(self, session, criteria, for_stats=False):
        query = session.query(models.Url)
        # Check if criteria is url search
        if criteria.get('search', None):
            if criteria.get('url', None):
                if isinstance(criteria.get('url'), list):
                    criteria['url'] = criteria['url'][0]
                query = query.filter(models.Url.url.like(
                    '%' + criteria['url'] + '%'))
        else:  # If not search
            if criteria.get('url', None):
                if isinstance(criteria.get('url'), (str, unicode)):
                    query = query.filter_by(url=criteria['url'])
                if isinstance(criteria.get('url'), list):
                    query = query.filter(
                        models.Url.url.in_(criteria['url']))
        # For the following section doesn't matter if filter/search because
        # it doesn't make sense to search in a boolean column :P
        if criteria.get('visited', None):
            if isinstance(criteria.get('visited'), list):
                criteria['visited'] = criteria['visited'][0]
            query = query.filter_by(
                visited=self.config.ConvertStrToBool(criteria['visited']))
        if criteria.get('scope', None):
            if isinstance(criteria.get('scope'), list):
                criteria['scope'] = criteria['scope'][0]
            query = query.filter_by(
                scope=self.config.ConvertStrToBool(criteria['scope']))
        if not for_stats:  # Query for stats can't have limit and offset
            try:
                if criteria.get('offset', None):
                    if isinstance(criteria.get('offset'), list):
                        criteria['offset'] = criteria['offset'][0]
                    query = query.offset(int(criteria['offset']))
                if criteria.get('limit', None):
                    if isinstance(criteria.get('limit'), list):
                        criteria['limit'] = criteria['limit'][0]
                    query = query.limit(int(criteria['limit']))
            except ValueError:
                raise InvalidParameterType(
                    "Invalid parameter type for transaction db")
        return query

    def GetAll(self, Criteria, target_id=None):
        Session = self.target.GetUrlDBSession(target_id)
        session = Session()
        query = self.GenerateQueryUsingSession(session, Criteria)
        results = query.all()
        return (self.DeriveUrlDicts(results))

    def SearchAll(self, Criteria, target_id=None):
        Session = self.target.GetUrlDBSession(target_id)
        session = Session()
        # Three things needed
        # + Total number of urls
        # + Filtered url
        # + Filtered number of url
        total = session.query(models.Url).count()
        filtered_url_objs = self.GenerateQueryUsingSession(
            session,
            Criteria).all()
        filtered_number = self.GenerateQueryUsingSession(
            session,
            Criteria,
            for_stats=True).count()
        return ({
                    "records_total": total,
                    "records_filtered": filtered_number,
                    "data": self.DeriveUrlDicts(
                        filtered_url_objs)
                })
