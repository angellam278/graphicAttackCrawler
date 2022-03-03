# python 3
# https://rubikscode.net/2021/06/21/scraping-images-with-python/

import logging
#import urllib2
# from urllib.request import urlopen
#from urllib3.request import urlopen
# from urllib.parse import urljoin
import requests
# other options: scrapy, selenium but going with beautifulSoup first
from bs4 import BeautifulSoup
import shutil
import os
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
import selenium.webdriver.support.expected_conditions as EC
from selenium.common.exceptions import TimeoutException


def download_image(image_url, download_name):
    # request image
    response = requests.get(image_url, stream=True)

    # prepare file directory
    file_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images_bs")
    if not os.path.exists(file_dir):
        os.mkdir(file_dir)
    file_path = os.path.join(file_dir, "{}.gif".format(download_name))
    # save file
    print("saving -> {}".format(file_path))
    file = open(file_path, 'wb')
    response.raw.decode_content = True
    shutil.copyfileobj(response.raw, file)

    del response

    return file_dir

def load_js_page(my_url):
    # because webpage is js rendered, cannot just get the html elements
    # https://stackoverflow.com/questions/54274458/scrape-pictures-from-javascript-rendered-webpage
    # use safari developer driver to simulate loading of webpage (to run its js and generate the images)
    driver = webdriver.safari.webdriver.WebDriver()
    # maximize window to get max number of gifs
    driver.maximize_window()
    driver.get(my_url)

    return driver

def get_img_giphy(my_url = 'https://giphy.com/', scroll_max = 5):
    driver = load_js_page(my_url)

    # wait for the cookies popup and click agree so page continues to load
    id_locator = (By.ID, "didomi-notice-agree-button")
    element= WebDriverWait(driver, 100).until(EC.presence_of_element_located(id_locator))
    p_element = driver.find_element(*id_locator)
    p_element.click()

    # class selector to wait for giphy-img-loaded class to appear (after each scroll)
    class_locator = (By.CLASS_NAME, "giphy-img-loaded")

    # https://stackoverflow.com/questions/33094727/selenium-scroll-till-end-of-the-page
    img_count = 0
    scroll_count = 0
    while scroll_count < scroll_max:
        # scroll
        driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
        scroll_count += 1

        try:
            # wait for giphy-img-loaded class
            element_loaded= WebDriverWait(driver, 50).until(EC.presence_of_element_located(class_locator))
            # WHEN ALL GIPHY IS LOADED
            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            # find all images
            for source in soup.find_all('img'):
                try:
                    # get src if any
                    src = source['src']
                    # download if possible
                    # some has unloaded URL like: data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7
                    download_image(src, src.split("/")[-2]);
                    img_count += 1
                except Exception:
                    continue
        except TimeoutException:
            print("time out")
            break

    print("total image checked: {}".format(img_count))

def get_img_tenor(my_url = 'https://tenor.com/', scroll_max = 5):
    driver = load_js_page(my_url)

    # https://stackoverflow.com/questions/33094727/selenium-scroll-till-end-of-the-page
    img_count = 0
    scroll_count = 0
    while scroll_count < scroll_max:
        # scroll
        driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
        scroll_count += 1

        try:
            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            # find all images
            for source in soup.find_all('img'):
                try:
                    # get src if any
                    src = source['src']
                    if src.endswith(".gif"):
                        # download if possible
                        download_image(src, src.split("/")[-1]);
                    img_count += 1
                except Exception:
                    continue
        except TimeoutException:
            print("time out")
            break

    print("total image checked: {}".format(img_count))

if __name__ == '__main__':
    get_img_tenor()

