# python 3
# scraping code reference: https://rubikscode.net/2021/06/21/scraping-images-with-python/
# image evaluation code reference: https://github.com/seanjoo4/DURIResearch/blob/master/src/Pixel.java

import logging
import argparse
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
import sqlite3
from PIL import Image

LOGGER = logging.getLogger(__name__)
COMPATIBLE = 128
# to connect and update the database in code
# NOTE: we are committing to database on every change
# (not efficient, but safe when we don't have a time limit to run this on)
DB = None
DB_CONN = None

def download_image(image_url, download_name):
    """
    Args:
        - *image_url* (string) url to .gif to download (doesn't need to end with .gif)
        - *download_name* (string) name to save file to

    Returns:
    - *file_path* (string) full path to saved file on computer
    """
    # request image
    response = requests.get(image_url, stream=True)

    # prepare file directory
    file_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images_bs")
    if not os.path.exists(file_dir):
        os.mkdir(file_dir)
    file_path = os.path.join(file_dir, "{0}.gif".format(download_name))
    # save file
    file = open(file_path, 'wb')
    response.raw.decode_content = True
    shutil.copyfileobj(response.raw, file)

    del response

    LOGGER.debug("saving -> %s", file_path)

    return file_path

def load_js_page(my_url):
    """
    Args:
        - *my_url* (string) url to webpage

    Returns:
    - *driver* (WebDriver) to simulate js loading page
    """
    # because webpage is js rendered, cannot just get the html elements
    # https://stackoverflow.com/questions/54274458/scrape-pictures-from-javascript-rendered-webpage
    # use safari developer driver to simulate loading of webpage (to run its js and generate the images)
    driver = webdriver.safari.webdriver.WebDriver()
    # maximize window to get max number of gifs
    driver.maximize_window()
    driver.get(my_url)

    return driver

def get_img_giphy(my_url="https://giphy.com/", scroll_max=5):
    """
    Crawls giphy (each web has different crawl structure)

    Args:
        - *my_url* (string) url to webpage
        - *scroll_max* (int) max times to scroll the page
    """
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
            element_loaded= WebDriverWait(driver, 50).until(
                EC.presence_of_element_located(class_locator)
            )
            # WHEN ALL GIPHY IS LOADED
            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            # find all images
            for source in soup.find_all('img'):
                try:
                    # get src if any
                    src = source['src']
                except Exception:
                    continue
                else:
                    # download if possible
                    # some has unloaded URL like:
                    # data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7
                    if src.endswith(".gif"):
                        # download if possible
                        evaluate_and_log(src)
                        img_count += 1
                    img_count += 1
        except TimeoutException:
            print("time out")
            break

    LOGGER.info("Total GIFs checked: %s", img_count)

def get_img_tenor(my_url="https://tenor.com/", scroll_max=5):
    """
    Crawls tenor (each web has different crawl structure)

    Args:
        - *my_url* (string) url to webpage
        - *scroll_max* (int) max times to scroll the page
    """
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
                except Exception:
                    continue
                else:
                    if src.endswith(".gif"):
                        # download if possible
                        evaluate_and_log(src)
                        img_count += 1
        except TimeoutException:
            print("time out")
            break

    LOGGER.info("Total GIFs checked: %s", img_count)

def evaluate_and_log(image_src):
    """
    If not already in our databsae,
    download the given image url, evaluate and log its danger level.

    Args:
        - *image_src* (string) url to image on web
    """
    # check if alraedy evaluated and in DB, dont do again (So we will also store the ones without danger)
    if (DB.execute(
        """ SELECT one, two FROM mytable WHERE one = '{0}'; """.format(image_src)
    )):
        LOGGER.debug("[Skipping] Image already evaluated: %s", image_src)
        return

    downloaded_img = download_image(image_src, image_src.split("/")[-1])
    danger_level = evaluate_image(downloaded_img)

    # log in database
    LOGGER.debug("Logging in DB: %s, %s", image_src, danger_level)
    DB.execute(
        """ INSERT INTO mytable (one,two) VALUES('{0}', {1}); """.format(
            image_src, danger_level
        )
    )
    # commit any changes to DB
    DB_CONN.commit()

    # delete image
    LOGGER.debug("removing evaluated image -> %s", downloaded_img)
    os.remove(downloaded_img)

def get_intensity(r, g, b):
    """
    Adapted from java code to get image intensity

    Args:
        - *r* (int) red
        - *g* (int) green
        - *b* (int) blue

    Returns:
        (int)
    """
    # intensity level (luminance) range of 0.0 to 255.0
    # values from the java code
    return 0.299 * r + 0.587 * g + 0.114 * b

def get_brightness(intensity):
    """
    Adapted from java code to get image brightness

    Args:
        - *intensity* (int)

    Returns:
        (int)
    """
    return 413.435 * pow(0.002745 * intensity + 0.0189623, 2.2);

def is_compatible(intensity_a, intensity_b):
    """
    Adapted from java code to see if the differences between the
    given intensities are safe (under given COMPATIBLE value)

    Args:
        - *intensity_a* (int)
        - *intensity_b* (int)

    Returns:
        (boolean)
    """
    return abs(intensity_a - intensity_b) < COMPATIBLE;

def is_hz_dangerous(duration):
    """
    Adapted from java code to see if the hz of gif is safe

    Args:
        - *duration* (int)

    Returns:
        (boolean)
    """
    # one Cycle/Millisecond is equal to 1000 Hertzs.
    hz = 1/(duration/1000)
    LOGGER.debug("hz: %s", hz)
    if hz >= 3 and hz <= 30:
        return True
    return False

def evaluate_image(image_path):
    """
    Evaluate the frames, hz and color brightness of the gifs.
    Outputs a danger level. 0 being safe.

    Args:
        - *image_path* (string) full path to image on local computer

    Returns:
        (int) 0 = safe, 1 = risky, 2 = dangerous, 3 = extreme
    """
    # returns 0 if safe
    LOGGER.info("Evaluating image: %s", image_path)

    # one dangerous frame will be flagged as danger (TODO is it too low?)
    danger_level = 0
    frame_count = 0

    if not image_path.endswith(".gif"):
        LOGGER.error("Image not gif (skipped): %s", image_path)
        return

    with Image.open(image_path) as im:

        # Get the width and hight of the image for iterating over
        width, height = im.size
        LOGGER.debug("Image dimension: %s x %s", width, height)

        # total gif duration
        total_duration = 0
        # get total frames
        frame_count = im.n_frames
        diff_frame_count = 0 # to average danger level
        LOGGER.debug("Total frames: %s", frame_count)

        # store first frame's info (so we don't have to check if frame != 0 every frame)
        im.seek(0)
        # with pix[1, 1] GIF gets single value because
        # GIF pixels refer to one of the 256 values in the GIF color palette.
        # GIFs are pallettized, whereas JPEGs are RGB.
        # The act of transforming the image disposes of the palette.
        rgb_im = im.convert('RGB')
        # storing pixel's (R,G,B) values in a 2D array [w][h]
        prev_frame_buffer = []
        for w in range(width):
            # pixel data per col
            column_buffer = []
            for h in range(height):
                # Get the RGB Value of the a pixel of an image
                r,g,b = rgb_im.getpixel((w, h))
                column_buffer.append((r,g,b))
            prev_frame_buffer.append(column_buffer)

        # evaluating gif starting from second frame
        for i in range(1, frame_count):
            # milliseconds
            frame_duration = im.info.get("duration", 0)
            total_duration += frame_duration

            # values to later evaluate
            compatible_count = 0 # total number of compatible pixels
            prev_total_intensity = 0 # previous frame's total intensity
            total_intensity = 0 # current frame's total intensity
            different_pixel_count = 0 # total number of different pixels
            difference = 0 # total diff in pixel value

            # get frame and convert to RGB for every frame
            im.seek(i)
            rgb_im = im.convert('RGB')
            # ((rgb))
            frame_buffer = []
            # read frame by columns
            for w in range(width):
                frame_col_buffer = []
                for h in range(height):
                    # Get the RGB Value of the a pixel of an image
                    r,g,b = rgb_im.getpixel((w, h))
                    frame_col_buffer.append((r,g,b))

                    prev_frame_r, prev_frame_g, prev_frame_b = prev_frame_buffer[w][h]

                    # if pixel has different colors from prev frame then evaluate
                    if (prev_frame_r != r and prev_frame_g != g and prev_frame_b != b):
                        # only calculate previous intensity when needed
                        prev_intensity = get_intensity(prev_frame_r, prev_frame_g, prev_frame_b)
                        intensity = get_intensity(r, g, b)
                        prev_total_intensity += prev_intensity
                        total_intensity += intensity
                        # get total differences
                        difference += (abs(prev_frame_r - r) \
                            + abs(prev_frame_g - g) \
                            + abs(prev_frame_b - b))
                        if (is_compatible(intensity, prev_intensity)):
                            compatible_count += 1
                        # increment number of different pixels
                        different_pixel_count += 1

                frame_buffer.append(frame_col_buffer)

            # store current and previous
            prev_frame_buffer = frame_buffer

            if not different_pixel_count:
                # skip if all pixels in the previous and current frames are the same
                continue
            diff_frame_count += 1

            # evaluating
            eval_count = 0 # to be incremented when a test failed (unsafe)
            total_pixel_values = width * height * 3;
            different_pixel_percentage = different_pixel_count / total_pixel_values
            # TODO why java says its not compatible count?
            different_percentage = (compatible_count / different_pixel_count) * 100
            danger_percent = different_pixel_percentage / different_percentage

            LOGGER.debug("The total amount of pixels are: %s", total_pixel_values)
            LOGGER.debug("The percentage of dangerous Pixels are: %s percent", danger_percent)
            if danger_percent > 30:
                LOGGER.debug("The percentage of dangerous pixels are dangerous.")
                eval_count += 1

            if is_hz_dangerous(frame_duration):
                LOGGER.debug("This GIF's Hz is in the range of being dangerous.")
                eval_count += 1
            else:
                LOGGER.debug("This GIF's Hz is in the range of being safe.")

            # Normalizing the value of different pixels for accuracy(average pixels per color component)
            avg_different_pixels = difference / total_pixel_values
            # There are 255 values of pixels in total
            percentage = (avg_different_pixels / 255) * 100;
            LOGGER.debug("Difference Percentage-->%s", percentage)

            # brightness/intensity
            avg_intensity = total_intensity / total_pixel_values;
            avg_prev_intensity = prev_total_intensity / total_pixel_values;
            LOGGER.debug(
                "This is the average intensity of the previous frame: %s",
                avg_prev_intensity
            )
            LOGGER.debug(
                "This is the average intensity of the current frame: %s",
                avg_intensity
            )
            avg_intensity_ratio = \
                min(avg_intensity, avg_prev_intensity) / max(avg_intensity, avg_prev_intensity)
            if avg_intensity_ratio <= 0.55:
                LOGGER.debug(
                    "Average intensity ratio between current and previous frame: %s is dangerous",
                    avg_intensity_ratio
                )
                eval_count += 1

            danger_level += eval_count
            LOGGER.debug("-------------------------------------------------------\n")

    # report final image evaluation results
    LOGGER.debug("total duration time for the GIF is %s milliseconds", total_duration)

    LOGGER.debug("danger_level: %s", danger_level)
    LOGGER.debug("frame_count: %s", frame_count)
    LOGGER.debug("diff_frame_count: %s", diff_frame_count)
    # averaging the danger level per frame TODO: Or should not use average? is one frame enough to mark as danger?
    danger_level = danger_level/diff_frame_count
    LOGGER.debug("average danger_level: %s", danger_level)
    if (danger_level == 1):
        LOGGER.info("This GIF is risky")
        # NOTE right now almost all is flagged as risky
    elif (danger_level == 2):
        LOGGER.info("This GIF is dangerous")
    elif (danger_level == 3):
        LOGGER.info("This GIF is extreme")
    else:
        LOGGER.info("This GIF is safe to watch")
    LOGGER.debug("=======================================================\n")

    # close image
    im.close()
    return danger_level


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Web Crawler to find dangerous gifs')
    # type file.py -d to enter debug mode
    parser.add_argument('-d', dest='debug', action='store_true', help='debug mode')
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
        LOGGER.setLevel(level=logging.DEBUG)
        LOGGER.debug("*** Debug Mode ***")
    else:
        logging.basicConfig(level=logging.INFO)
        LOGGER.setLevel(level=logging.INFO)

    # evaluate_image("/Users/angellam/Desktop/Purdue/spring2022/DURI_research/DURIResearch-master/test2.gif")
    # TODO make db an input?
    db_path = "/Users/angellam/Desktop/Purdue/spring2022/DURI_research/crawler/graphicAttackCrawler/test.db"
    if os.path.exists(db_path):
        LOGGER.info("Writing to Database: %s", db_path)
        DB_CONN = sqlite3.connect(db_path)
        # to be able to run the execute command
        DB = DB_CONN.cursor()
        # begin crawling
        get_img_tenor()
    else:
        LOGGER.error("Database missing")
