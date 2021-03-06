# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://doc.scrapy.org/en/latest/topics/item-pipeline.html


class Spider1688Pipeline(object):
    def process_item(self, item, spider):
        return item

# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://doc.scrapy.org/en/latest/topics/item-pipeline.html
import pymongo
import urllib.request
import os
import concurrent.futures
import socket
import logging
import ast
from scrapy.utils.log import configure_logging
from scrapy.exceptions import DropItem

class MediaPipeline(object):
    def __init__(self, mongo_uri, mongo_db):
        # configure_logging(install_root_handler=False)
        logging.basicConfig(
            filename='/mnt/e/pipeline_log.txt',
            format='%(levelname)s: %(message)s',
            level=logging.ERROR
        )
        self.e = concurrent.futures.ThreadPoolExecutor(max_workers=6)
        
        socket.setdefaulttimeout(30)

        self.ped_bed_set = set()
        self.ped_bed_store_set = set()

        self.client = pymongo.MongoClient(mongo_uri)
        self.db = self.client[mongo_db]

        self.get_ped_bed_from_mongodb()
        self.get_company_from_mongodb()
        pass

    def auto_download(self, url, file_path):
        try:
            self.e.submit(urllib.request.urlretrieve,url, file_path)
        except socket.timeout:
            count = 1
            while count < 10:
                try:
                    self.e.submit(urllib.request.urlretrieve,url, file_path)
                    break
                except socket.timeout:
                    err_info = 'Reloading for %d time' %count if count == 1 else 'Reloading for %d times'%count
                    logging.error(err_info)
                    count += 1
            if count == 10:
                logging.error('downloading picture failed!')

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            mongo_uri = crawler.settings.get('MONGO_URI'),
            mongo_db = crawler.settings.get('MONGO_DATABASE', 'noname')
        )

    def get_ped_bed_from_mongodb(self):
        for bed_name in self.db.ped_bed.find({},{"product_name":1, "_id":0}):
            bed = bed['product_name']
            self.ped_bed_set.add(bed)
    def get_company_from_mongodb(self):
        for company in self.db.ped_bed_store.find({},{"company_name":1, "_id":0}):
            name = company['company_name']
            self.ped_bed_store_set.add(name)
    
    def process_item(self, item, spider):
        if item['item_id'] == 'pet_bed':
            if item['product_name'] in self.ped_bed_set:
                raise DropItem('Drop exist item')
            else:
                self.ped_bed_set.add(item['product_name'])
            root_folder = '/mnt/e/spider-download/' + spider.name +'/' + item['product_number'] + '/'
            pre_img_folder = root_folder + 'pre_images/'
            origin_img_folder = root_folder + 'original_images/'

            # 视频路径
            video_folder = root_folder + "video/"
            try:
                if not os.path.exists(pre_img_folder):
                    os.makedirs(pre_img_folder, mode=0o777)
                if not os.path.exists(origin_img_folder):
                    os.makedirs(origin_img_folder, mode=0o777)
                if not os.path.exists(video_folder):
                    os.makedirs(video_folder, mode=0o777)
            except OSError as e:
                print("mkdir error" + e.strerror)

            video_url = item['product_video']
            video_hash = str(abs(hash(video_url)) % (10**8)) + '.mp4'
            self.auto_download(video_url, video_folder  + video_hash) 

            preview_images = []
            original_images = []
            for image in item['product_image']:
                preview_images.append(ast.literal_eval(image).get('preview'))
                original_images.append(ast.literal_eval(image).get('original'))
            # 400 X 400的预览图
            for pre_img_url in preview_images:
                img_hash = str(abs(hash(pre_img_url)) % (10**8)) + '.jpg'
                self.auto_download(pre_img_url, pre_img_folder  + img_hash) 
            # 原始大图
            for origin_img_url in original_images:
                img_hash = str(abs(hash(origin_img_url)) % (10**8)) + '.jpg'
                self.auto_download(origin_img_url, origin_img_folder + img_hash) 
        elif item['item_id'] == '1688_store':
            if  item['company_name'] in self.ped_bed_store_set:
                raise DropItem('store exist')

        return item

class MongoPipeline(object):
    petBd_collection = 'pet_bed'
    company_1688_collection = 'pet_bed_store'

    def __init__(self,  mongo_uri, mongo_db):
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.e = concurrent.futures.ThreadPoolExecutor(max_workers=6)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            mongo_uri = crawler.settings.get('MONGO_URI'),
            mongo_db = crawler.settings.get('MONGO_DATABASE', 'noname')
        )

    def open_spider(self, spider):
        self.client = pymongo.MongoClient(self.mongo_uri)
        self.db = self.client[self.mongo_db]

    def close_spider(self, spider):
        self.client.close()

    def process_item(self, item, spider):
        if item['item_id'] == '1688_store':
            self.db[self.company_1688_collection].insert_one(dict(item))
        elif item['item_id'] == 'pet_bed':
            self.db[self.petBd_collection].insert_one(dict(item))
        return item


