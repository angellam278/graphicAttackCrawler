# python 3
# https://rubikscode.net/2021/06/21/scraping-images-with-python/

import logging
from urllib.parse import urljoin
import requests
# other options: scrapy, selenium but going with beautifulSoup first
from bs4 import BeautifulSoup
import shutil
import os

logging.basicConfig(
    format='%(asctime)s %(levelname)s:%(message)s',
    level=logging.INFO)

class Crawler:

    def __init__(self, urls=[]):
        self.visited_urls = []
        self.urls_to_visit = urls

    def download_url(self, url):
        # send request
        return requests.get(url).text

    def get_linked_urls(self, url, html):
        image_info = []
        soup = BeautifulSoup(html, 'html.parser')
        # find all images: all elements from HTML DOM that have tag <a> and class entry-featured-image-url
        #for link in soup.find_all("a", class_='entry-featured-image-url'):
        # TODO: do for giphy web?
        for link in soup.find_all("a"):
            # find images for all links
            image_info.append(self.find_images(link, True))
            path = link.get('href')
            if path and path.startswith('/'):
                path = urljoin(url, path)
            yield path

    def find_images(self, alink, download=False):
        image_tag = alink.findChildren("img")
        image_src = ""
        img_alt = ""
        if image_tag:
            image_src = image_tag[0]["src"]
            if not image_src.endswith(".gif"):
                # only look for gifs
                return ("", "")
            img_alt = image_tag[0]["alt"]
            print("IMAGE: {}, {}".format(image_src, img_alt))
            if download:
                self.download_image(image_src)
            # get image source and alternative description
        return (image_src, img_alt)

    def download_image(self, image):
        response = requests.get(image, stream=True)
        # remove all spaces and special characters
        realname = ''.join(e for e in image[1] if e.isalnum())
        file_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images_bs")
        if not os.path.exists(file_dir):
            os.mkdir(file_dir)
        file_path = os.path.join(file_dir, "{}.gif".format(realname))
        print("saving -> {}".format(file_path))
        file = open(file_path, 'wb')

        response.raw.decode_content = True
        shutil.copyfileobj(response.raw, file)
        del response

    def add_url_to_visit(self, url):
        if url not in self.visited_urls and url not in self.urls_to_visit:
            self.urls_to_visit.append(url)

    def crawl(self, url):
        html = self.download_url(url)
        for url in self.get_linked_urls(url, html):
            self.add_url_to_visit(url)

    def run(self):
        # recursively call through related links
        while self.urls_to_visit:
            url = self.urls_to_visit.pop(0)
            logging.info(f'Crawling: {url}')
            try:
                self.crawl(url)
            except Exception:
                logging.exception(f'Failed to crawl: {url}')
            finally:
                self.visited_urls.append(url)

if __name__ == '__main__':
    Crawler(urls=['https://giphy.com/']).run()