#import Leap
import Leap, sys, thread, time
from curses import wrapper
import curses
import time

class LineFunc(object):
    """ Represents y=mx+b """
    def __init__(self, slope, y_intercept):
        self.slope = slope
        self.y_intercept = y_intercept

    def __call__(self, x):
        return x * self.slope + self.y_intercept

    def __str__(self):
        return 'f(x) = {0} * x + {1}'.format(self.slope, self.y_intercept)


class Box(object):
    def __init__(self, top, left, height, width):
        self.top = top
        self.left = left
        self.height = height
        self.width = width

    def clamp(self, point):
        y = point[0]
        x = point[1]
        if y < self.top:
            y = self.top
        if y > self.top + self.height:
            y = self.top + self.height
        if x < self.left:
            x = self.left
        if x > self.left + self.width:
            x = self.left + self.width
        return (y, x)

    def contains(self, point):
        y, x = point
        return y >= self.top and \
            y <= self.top + self.height and \
            x >= self.left and \
            x <= self.left + self.width

    def expand_to_include(self, point, exclusive_bottom=True, exclusive_right=True):
        bottom_pad = 1 if exclusive_bottom else 0
        right_pad = 1 if exclusive_right else 0
        self.top = min(self.top, point[0])
        self.left = min(self.left, point[1])
        self.height = max(self.height, point[0] - self.top + bottom_pad)
        self.width = max(self.width, point[1] - self.left + right_pad)


class BoxTranslator(object):
    """ Maps points from one box to another proportionally. """
    def __init__(self, input_box, output_box):
        y_tx_slope = 1.0 * output_box.height / input_box.height
        x_tx_slope = 1.0 * output_box.width / input_box.width
        self.y_tx = LineFunc(y_tx_slope, (output_box.top - input_box.top) * y_tx_slope)
        self.x_tx = LineFunc(x_tx_slope, (output_box.left - input_box.left) * x_tx_slope)

    def __call__(self, point):
        """ Map input box location to output_box location. """
        return (self.y_tx(point[0]), self.x_tx(point[1]))
        
        
def project_leap_vector(vector):
    return (vector[2], vector[0])


class HandsApp(object):
    def __init__(self, win):
        self.leap_controller = Leap.Controller()
        self.win = win
        self.win.clear()
        self.init_boxes()
        self.ensure_translator(None)
        # ISSUE: what are the dimensions of the LeapMotion's inputs?
        #  One option is to use the "interaction box", but that's not really a total bounding box.
        #  Another option is to be adaptive - to scale to the largest values seen.  (Or largest values seen over the last N frames, a more complex case.)
        #  We will start out with something hard-coded experimentally based on my own desktop, and complicate things from there as proves necessary to support the general case.

    def init_boxes(self):
        self.input_box = Box(0, 0, 1, 1)    # will expand; degenerate-case size
        self.output_box = Box(0, 0, self.win.getmaxyx()[0] - 1, self.win.getmaxyx()[1] - 1)

    def ensure_translator(self, input_point):
        """
        Ensure the point translator exists and is configured for the largest range of input
         values we've seen so far.  (Expand that range and re-init the translator using
         the specified latest input point, if necessary.)
        """
        if input_point:
            if not self.input_box.contains(input_point):
                self.input_box.expand_to_include(input_point)

        self.box_translator = BoxTranslator(self.input_box, self.output_box)

    def get_frame_finger_bones(self):
        """
        Gets a frame from LeapMotion controller and returns a list of point-triplets
         corresponding to the start, mid, and end points, in (Y,X) 2D projection, of
         all the bones in all the fingers in the frame.
        """
        bones = []
        frame = self.leap_controller.frame()
        for finger in frame.fingers:
            for bone in [finger.bone(bone_id) for bone_id in range(4)]:
                if not bone.is_valid:
                    continue
                bone_start = project_leap_vector(bone.prev_joint)
                bone_mid = project_leap_vector(bone.center)
                bone_end = project_leap_vector(bone.next_joint)
                bones.append((bone_start, bone_mid, bone_end))
        return bones
                
    def run(self):
        self.win.nodelay(1)
        bone_paint_chars = ['*', 'x']
        
        counter = 0
        should_quit = False
        while(not should_quit):
            counter += 1
            if counter % 50 == 0:
                should_quit = self.win.getch() != -1
               
            self.win.clear()
            bones = self.get_frame_finger_bones()
            
            if not bones:
                self.win.addstr(0, 0, '(No fingers; any key to exit.)')
                self.win.refresh()
                time.sleep(.1)
                continue
            draw_fail = False
            for bone in bones:
                for i, point in enumerate(bone):
                    self.ensure_translator(point)
                    tx_point = self.output_box.clamp(self.box_translator(point))
                    try:
                        self.win.addstr(int(tx_point[0]), int(tx_point[1]), bone_paint_chars[i % len(bone_paint_chars)])
                    except Exception as ex:
                        draw_fail = True
                        self.win.clear()
                        self.win.addstr(0, 0, '({0},{1}) => ({2},{3})'.format(
                            round(point[0], 3), round(point[1], 3),
                            int(tx_point[0]), int(tx_point[1])))
                        self.win.addstr(1, 0, str(ex)[:self.output_box.width])
                        self.win.refresh()
                        time.sleep(1)
            if not draw_fail:
                self.win.move(self.output_box.top + self.output_box.height, self.output_box.left + self.output_box.width)
                self.win.refresh()

        self.win.refresh()

def app_entry(win):
    app = HandsApp(win)
    app.run()

if __name__ == '__main__':
    wrapper(app_entry)
