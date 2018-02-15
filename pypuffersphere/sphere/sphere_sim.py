import os 
import numpy as np
import pyglet
from pyglet.gl  import *
import time,sys,random,math,os


import timeit
wall_clock = timeit.default_timer

from pypuffersphere.utils import glskeleton,  gloffscreen, np_vbo, shader
from pypuffersphere.sphere import sphere
from pypuffersphere.utils.graphics_utils import make_unit_quad_tile
from pypuffersphere.sphere.sim_rotation_manager import RotationManager





def resource_file(fname):
    dir_path = os.path.dirname(os.path.realpath(__file__))        
    return os.path.join(dir_path, "..", fname)




def getshader(f):
    return resource_file(os.path.join("shaders", f))


def mkshader(verts, frags):
    return shader.shader_from_file([getshader(c) for c in verts], [getshader(c) for c in frags])

class SphereViewer:

    def make_quad(self):
        # create the vertex buffers that will be used to reproject the sphere
        self.fbo = gloffscreen.FBOContext(self.size, self.size)
        self.touch_fbo = gloffscreen.FBOContext(self.window_size[0], self.window_size[1], texture=False)

        self.finger_point_shader = mkshader(["sphere.vert", "finger_point.vert"], ["finger_point.frag"])     
        self.sphere_map_shader = mkshader(["sphere.vert", "sphere_map.vert"], ["sphere_map.frag"])        
        self.touch_shader = mkshader(["sphere.vert", "sphere_touch.vert"], ["sphere_touch.frag"])        
        self.quad_shader = mkshader(["sphere.vert", "quad.vert"], ["quad.frag"])        

        n_subdiv = 128        
        quad_indices, quad_verts, _ = make_unit_quad_tile(n_subdiv)    
        qverts = np_vbo.VBuf(quad_verts)      
        
        self.sphere_render = shader.ShaderVBO(self.sphere_map_shader, quad_indices, 
                                         buffers={"position":qverts},
                                         textures={"quadTexture":self.fbo.texture},
                                         vars={"grid_bright":self.debug_grid})



        # this will hold positions of active touches for drawing
        self.touch_pts = np.zeros((32, 2))
        
        self.touch_buf = np_vbo.VBuf(self.touch_pts)
        self.touch_render = shader.ShaderVBO(self.finger_point_shader, 
                                         np.arange(len(self.touch_pts)), 
                                         buffers={"position":self.touch_buf},
                                         primitives=GL_POINTS)

        # simple quad render for testing
        world_indices, world_verts, world_texs = make_unit_quad_tile(1)            

        self.world_render = shader.ShaderVBO(self.quad_shader, world_indices, 
                                         buffers={"position":np_vbo.VBuf(world_verts),
                                         "tex_coord":np_vbo.VBuf(world_texs)},
                                         textures={"quadTexture":self.world_texture.texture})

        # for getting touches back
        self.sphere_touch = shader.ShaderVBO(self.touch_shader, quad_indices, 
                                            buffers={"position":qverts})

        
    def test_render(self):
        self.world_render.draw(n_prims=0)
      

    def __init__(self, sphere_resolution=1024, window_size=(800,600), background=None, exit_fn=None, simulate=True, auto_spin=False, draw_fn=None, tick_fn=None, 
        debug_grid=0.1, test_render=False):
        self.simulate = simulate
        self.debug_grid = debug_grid # overlaid grid on sphere simulation
        self.size = sphere_resolution
        if not test_render:            
            self.draw_fn = draw_fn
        else:
            self.draw_fn = self.test_render # simple test function to check rendering
        self.exit_fn = exit_fn
        self.tick_fn = tick_fn        
        self.window_size = window_size

        
        self.world_texture = pyglet.image.load(resource_file("data/azworld.png"))
        self.rotation_manager = RotationManager(auto_spin=auto_spin)
        self.skeleton = glskeleton.GLSkeleton(draw_fn = self.redraw, resize_fn = self.resize, 
        tick_fn=self.tick, mouse_fn=self.mouse, key_fn=self.key, window_size=window_size)

        

        if not self.simulate:
            cx = window_size[0] - sphere_resolution
            cy = window_size[1] - sphere_resolution            
            glViewport(cx/2,0,sphere_resolution,sphere_resolution)
            
        self.make_quad()
      
    def resize(self, w, h):
        if not self.simulate:
            cx = w - self.size
            cy = h - self.size            
            glViewport(cx/2,cy/2,self.size,self.size)
        else:            
            glViewport(0,0,w,h)
                        
    def start(self):
        self.skeleton.main_loop()
        
    def mouse(self, event, x=None, y=None, dx=None, dy=None, buttons=None, modifiers=None, **kwargs):
        
        if buttons is not None:
            # drag sphere with left mouse
            if buttons & pyglet.window.mouse.LEFT:
                if event=="press":    
                    self.rotation_manager.press(x,y)                
                if event=="drag":
                    self.rotation_manager.drag(x,y)    
                if event=="release":
                    self.rotation_manager.release(x,y)    
            
            # simulated touches with right mouse
            if buttons & pyglet.window.mouse.RIGHT:
                if event=="press":    
                    self.rotation_manager.touch_down(x,y)
                if event=="drag":
                    self.rotation_manager.touch_drag(x,y)
                if event=="release":
                    self.rotation_manager.touch_release(x,y)
                
                
    def key(self, event, symbol, modifiers):
        if symbol==pyglet.window.key.ESCAPE:            
            if self.exit_fn:
                self.exit_fn()
            pyglet.app.exit()
            sys.exit(0)
                        
    
    def tick(self):        
        if self.tick_fn:
            self.tick_fn()
                
        self.rotation_manager.tick()
            
    
                        
    def redraw(self):  
        glEnable(GL_BLEND)        
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        # clear the screen
        glClearColor(0.1, 0.1, 0.1, 1)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # enable point drawing for touch point
        glEnable(GL_POINT_SMOOTH)
        glEnable(GL_VERTEX_PROGRAM_POINT_SIZE)
                 
        
        if not self.simulate:
            self.draw_fn()
        else:
            # draw onto the FBO texture
            with self.fbo as f:
                self.draw_fn()                
                pt = self.rotation_manager.get_touch_point()
                self.touch_pts[0,:] = pt
                self.touch_buf.set(self.touch_pts)
                self.touch_render.draw(n_prims=0)
                

            # render onto the screen using the sphere distortion shader    
            rotate, tilt = self.rotation_manager.get_rotation()
            self.sphere_render.draw(n_prims=0, vars={"rotate":np.radians(rotate), "tilt":np.radians(tilt)})
            
            
            # render the image for the touch point look up
            with self.touch_fbo as f:
            
                self.sphere_touch.draw(n_prims=0, vars={"rotate":np.radians(rotate), "tilt":np.radians(tilt)})
                
                pixel_data = (GLubyte * 4)()
                # get window coordinates
                mx, my = self.rotation_manager.get_mouse_pos()                
                
                # read the pixels, convert back to radians (from unsigned bytes)
                glReadPixels(mx, my, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, pixel_data)                                
                
                sphere_lat, sphere_lon = ((pixel_data[0] / 255.0) -0.5) * np.pi, ((pixel_data[1]/255.0)-0.5)*2*np.pi                
                # tell the touch manager where the touch is
                self.rotation_manager.set_sphere_touch(sphere_lat, sphere_lon)

        
    
SPHERE_WIDTH = 2560
SPHERE_HEIGHT = 1600
SPHERE_SIZE = 1920 # estimated to compensate for the partial sphere coverage

def make_viewer(**kwargs):
    sim = False
    if "--test" in sys.argv:
        sim = True
    
    if sim:
        s = SphereViewer(sphere_resolution=1600, window_size=(800, 800), background=None, simulate=True, **kwargs)
        print("Simulating")
    else:        
        s = SphereViewer(sphere_resolution=SPHERE_SIZE, window_size=(SPHERE_WIDTH,SPHERE_HEIGHT), background=None, simulate=False, **kwargs)
        print("Non-simulated")
    return s

