import cozmo
import asyncio
from Common.woc import WOC
from Instagram.InstagramAPI import InstagramAPI
from Common.colors import Colors
import speech_recognition as sr
import _thread
import time
import os
import sys

from cv2 import VideoWriter, VideoWriter_fourcc, imread, resize

sys.path.append(os.path.abspath('Instagram/'))

try:
    import numpy as np
except ImportError:
    print("Cannot import numpy: Do `pip3 install --user numpy` to install")

try:
    from PIL import Image
    from PIL import ImageFilter
except ImportError:
    print("Cannot import from PIL: Do `pip3 install --user Pillow` to install")

'''
@class CaptureImage
Cozmo takes a picture and uploads the image to Instagram
@author - Wizards of Coz
'''

class CaptureImage(WOC):
    FILTER_FOLDER_NAME = "Filters"              # Folder name where all the 14 filters generated are saved
    VIDEO_IMAGES_FOLDER_NAME = "VideoImages"    # Folder name where the images are saved
    OUTPUT_IMAGE_NAME = "thumbnail.jpg"         # Thumbnail Image name
    INSTAGRAM_USER_NAME = "wizardsofcoz"        # Enter your Instagram Username here
    INSTAGRAM_PASSWORD = ""                     # Enter your Instagram Password here or create a file "instagram.txt" and write the password there in the first line
    OUTPUT_VIDEO_NAME = "video.avi"             # Video name
    INSTAGRAM_FILE_NAME = "instagram.txt"       # Text file to store your password

    def __init__(self, *a, **kw):
        WOC.__init__(self)

        if os.path.exists(self.OUTPUT_VIDEO_NAME):
            os.remove(self.OUTPUT_VIDEO_NAME)

        if self.INSTAGRAM_PASSWORD == "":
            with open(self.INSTAGRAM_FILE_NAME) as f:
                self.INSTAGRAM_PASSWORD = f.readlines()[0];

        self.insta = InstagramAPI(self.INSTAGRAM_USER_NAME, self.INSTAGRAM_PASSWORD)
        self.insta.login()  # login

        cozmo.setup_basic_logging()
        cozmo.connect(self.run)

    async def run(self, coz_conn):
        asyncio.set_event_loop(coz_conn._loop)
        self.coz = await coz_conn.wait_for_robot()

        await self.start_program()

        while not self.exit_flag:
            await asyncio.sleep(0)
        self.coz.abort_all_actions()

    async def calc_pixel_threshold(self, image: Image):
        grayscale_image = image.convert('L')
        mean_value = np.mean(grayscale_image.getdata())
        return mean_value

    async def start_program(self):
        self.coz.camera.image_stream_enabled = True;
        await self.coz.set_lift_height(0).wait_for_completed();
        await self.coz.set_head_angle(cozmo.robot.MAX_HEAD_ANGLE/4).wait_for_completed()
        self.cubes = None
        look_around = self.coz.start_behavior(cozmo.behavior.BehaviorTypes.LookAroundInPlace)

        try:
            self.cubes = await self.coz.world.wait_until_observe_num_objects(1, object_type = cozmo.objects.LightCube,timeout=60)
        except asyncio.TimeoutError:
            print("Didn't find a cube :-(")
            return
        finally:
            look_around.stop()
            await self.coz.set_head_angle(cozmo.robot.MAX_HEAD_ANGLE, in_parallel= True).wait_for_completed()
            for cube in self.cubes:
                cube.set_lights(Colors.GREEN);
            self.coz.world.add_event_handler(cozmo.objects.EvtObjectTapped, self.on_object_tapped)

            self.found_meaningfulAudio = False;

            _thread.start_new_thread(self.start_Audio_Thread, ())

            self.latest_Image = None;

            self.face_dimensions = cozmo.oled_face.SCREEN_WIDTH, cozmo.oled_face.SCREEN_HALF_HEIGHT
            self.image_taken = False;

            self.handler1 = self.coz.world.add_event_handler(cozmo.camera.EvtNewRawCameraImage, self.on_raw_cam_image)

            self.do_final_anim = False;
            while True:
                if self.do_final_anim:
                    self.coz.abort_all_actions();
                    await self.coz.say_text(", Memory Captured").wait_for_completed()
                    await self.coz.play_anim("anim_pounce_success_02", loop_count=1, in_parallel=True).wait_for_completed()
                    break;
                else:
                    await asyncio.sleep(0.1);
            self.exit_flag = True

    async def on_raw_cam_image(self, event, *, image, **kw):
        self.latest_Image = image;
        resized_image = image.resize(self.face_dimensions, Image.BICUBIC)
        resized_image = resized_image.transpose(Image.FLIP_LEFT_RIGHT)
        pixel_threshold = await self.calc_pixel_threshold(resized_image)
        screen_data = cozmo.oled_face.convert_image_to_screen_data(resized_image, pixel_threshold=pixel_threshold)

        self.coz.display_oled_face_image(screen_data, 0.1 * 1000.0)

    async def caughtAudio(self, text):
        print("You said " + text);
        if "ea" in text or "ee" in text or "ie" in text:
            self.coz.set_all_backpack_lights(Colors.GREEN)
            self.found_meaningfulAudio = True;
            await self.clickPicture();
        else:
            self.coz.set_all_backpack_lights(Colors.RED)
            time.sleep(1);
            self.coz.set_backpack_lights_off();
            await self.captureAudio();

    async def captureAudio(self):
        if self.found_meaningfulAudio == False:
            r = sr.Recognizer()
            r.energy_threshold = 5000;
            with sr.Microphone(chunk_size=512) as source:
                audio = r.listen(source)

            try:
                text = r.recognize_google(audio);
                await self.caughtAudio(text);

            except sr.UnknownValueError:
                print("Google Speech Recognition could not understand audio")
                self.coz.set_all_backpack_lights(Colors.RED)
                await asyncio.sleep(1);
                self.coz.set_backpack_lights_off();
                await self.captureAudio();

            except sr.RequestError as e:
                print("Could not request results from Google Speech Recognition service; {0}".format(e))

    def start_Audio_Thread(self):
        # Record Audio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.captureAudio())

    async def clickPicture(self):
        self.image_taken = True;

        i = 0;
        while i < 3:
            for cube in self.cubes:
                cube.set_lights(Colors.GREEN);
                self.coz.set_all_backpack_lights(Colors.GREEN)
            await asyncio.sleep(0.2);
            for cube in self.cubes:
                cube.set_lights_off();
                self.coz.set_backpack_lights_off();
            await asyncio.sleep(0.2);
            i += 1

        await asyncio.sleep(0.1);

        for cube in self.cubes:
            cube.set_lights(Colors.RED);
            self.coz.set_all_backpack_lights(Colors.RED)

        if not os.path.exists(self.VIDEO_IMAGES_FOLDER_NAME):
            os.makedirs(self.VIDEO_IMAGES_FOLDER_NAME)
        self.max_count = 60;                                                 # Number of images to make the video
        cur_count = 0;
        while cur_count < self.max_count:
            self.latest_Image.save(self.VIDEO_IMAGES_FOLDER_NAME+"/image" + str(cur_count) + ".jpg");
            await asyncio.sleep(0.1);
            cur_count += 1;

        self.coz.world.remove_event_handler(cozmo.camera.EvtNewRawCameraImage, self.handler1);


        image = self.latest_Image

        resized_image = image.resize(self.face_dimensions, Image.BICUBIC)
        resized_image = resized_image.transpose(Image.FLIP_LEFT_RIGHT)
        grayscale_image = resized_image.convert('L')
        mean_value = np.mean(grayscale_image.getdata())
        screen_data = cozmo.oled_face.convert_image_to_screen_data(resized_image, pixel_threshold=mean_value)
        self.coz.display_oled_face_image(screen_data, 10000, in_parallel= True)

        img = image.convert('L')
        img.save(self.OUTPUT_IMAGE_NAME)

        # This block is to save filters for the images into an Images folder
        if not os.path.exists(self.FILTER_FOLDER_NAME):
            os.makedirs(self.FILTER_FOLDER_NAME)
        img.filter(ImageFilter.BLUR).save(self.FILTER_FOLDER_NAME+"/Blur.jpg")
        img.filter(ImageFilter.CONTOUR).save(self.FILTER_FOLDER_NAME+"/CONTOUR.jpg")
        img.filter(ImageFilter.DETAIL).save(self.FILTER_FOLDER_NAME+"/DETAIL.jpg")
        img.filter(ImageFilter.EDGE_ENHANCE).save(self.FILTER_FOLDER_NAME+"/EDGE_ENHANCE.jpg")
        img.filter(ImageFilter.EDGE_ENHANCE_MORE).save(self.FILTER_FOLDER_NAME+"/EDGE_ENHANCE_MORE.jpg")
        img.filter(ImageFilter.EMBOSS).save(self.FILTER_FOLDER_NAME+"/EMBOSS.jpg")
        img.filter(ImageFilter.FIND_EDGES).save(self.FILTER_FOLDER_NAME+"/FIND_EDGES.jpg")
        img.filter(ImageFilter.SMOOTH).save(self.FILTER_FOLDER_NAME+"/SMOOTH.jpg")
        img.filter(ImageFilter.SMOOTH_MORE).save(self.FILTER_FOLDER_NAME+"/SMOOTH_MORE.jpg")
        img.filter(ImageFilter.SHARPEN).save(self.FILTER_FOLDER_NAME+"/SHARPEN.jpg")
        img.filter(ImageFilter.MaxFilter).save(self.FILTER_FOLDER_NAME+"/MaxFilter.jpg")
        img.filter(ImageFilter.ModeFilter).save(self.FILTER_FOLDER_NAME+"/ModeFilter.jpg")
        img.filter(ImageFilter.MedianFilter).save(self.FILTER_FOLDER_NAME+"/MedianFilter.jpg")
        img.filter(ImageFilter.UnsharpMask).save(self.FILTER_FOLDER_NAME+"/UnsharpMask.jpg")

        # comment this to not upload a video
        await self.make_video_and_upload();


        # uncomment this blockto upload a photo instead of the video

        # self.insta = InstagramAPI(self.INSTAGRAM_USER_NAME, self.INSTAGRAM_PASSWORD)
        # self.insta.login()  # login
        # self.insta.uploadPhoto("output.jpg", "#memorieswithcozmo");

        for cube in self.cubes:
            cube.set_lights(Colors.GREEN)
            self.coz.set_all_backpack_lights(Colors.GREEN)

        self.do_final_anim = True;

    async def make_video_and_upload(self):
        outvid = self.OUTPUT_VIDEO_NAME
        fps = 24;
        size = (320, 240);
        is_color = 1;

        fourcc = VideoWriter_fourcc(*'XVID')
        vid = None
        images = []
        for i in range(0, self.max_count):
            images.append(self.VIDEO_IMAGES_FOLDER_NAME+"/image" + str(i) + ".jpg")

        print(images);

        for image in images:
            if not os.path.exists(image):
                raise FileNotFoundError(image)
            img = imread(image)
            if vid is None:
                if size is None:
                    size = img.shape[1], img.shape[0]
                vid = VideoWriter(outvid, fourcc, float(fps), size, is_color)
            if size[0] != img.shape[1] and size[1] != img.shape[0]:
                img = resize(img, size)
            vid.write(img)
        vid.release()

        self.insta.uploadVideo("video.avi", thumbnail=self.OUTPUT_IMAGE_NAME, caption="#memorieswithcozmo");

    async def on_object_tapped(self, event, *, obj, tap_count, tap_duration, **kw):
        # print("Received	a	tap	event", event)
        # print("Received	a	tap	event", obj.object_id)
        await self.clickPicture();

if __name__ == '__main__':
    CaptureImage()
