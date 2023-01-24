import logging
from math import sqrt

from scyjava import jimport
import scyjava
import jpype.imports
import json
import openpmd_api as io

scyjava.config.add_repositories({'scijava.public': 'https://maven.scijava.org/content/groups/public'})
scyjava.config.add_repositories({'jitpack.io': 'https://jitpack.io'})
scyjava.config.endpoints.append("net.imagej:imagej")
scyjava.config.endpoints.append("org.slf4j:slf4j-simple:1.7.25")
scyjava.config.endpoints.append("org.jetbrains.kotlin:kotlin-stdlib:1.7.20")
scyjava.config.endpoints.append('graphics.scenery:scenery:bc926503')

# scenery imports, they need to happen after the JVM has started
# so they are visible to Python
scyjava.start_jvm()
from graphics.scenery import SceneryBase
from graphics.scenery.backends import Renderer
from graphics.scenery import Hub
from graphics.scenery import Scene
from graphics.scenery import SceneryElement
from graphics.scenery import Settings
from graphics.scenery import DetachedHeadCamera
from graphics.scenery import Box
from graphics.scenery import PointLight
from graphics.scenery import ShaderMaterial
from graphics.scenery import InstancedNode
from graphics.scenery.numerics import Random
from org.joml import Vector3f

basepath = "../../3rdparty/openPMD-example-datasets/"
file = "example-3d/hdf5/data%T.h5"

# pass-through for ADIOS2 engine parameters
# https://adios2.readthedocs.io/en/latest/engines/engines.html
config = {'adios2': {'engine': {}, 'dataset': {}}}
config['adios2']['engine'] = {'parameters': {'Threads': '4'}}
config['adios2']['dataset'] = {'operators': [{'type': 'bzip2'}]}

System = jimport("java.lang.System")

print(System.getProperty("os.name"))
print(System.getProperty("java.version"))

series = io.Series(basepath + "/" + file, io.Access_Type.read_only,
                   json.dumps(config))

# Read all available iterations and print electron position data.
# Use `series.read_iterations()` instead of `series.iterations`
# for streaming support (while still retaining file-reading support).
# Direct access to `series.iterations` is only necessary for random-access
# of iterations. By using `series.read_iterations()`, the openPMD-api will
# step through the iterations one by one, and going back to an iteration is
# not possible once it has been closed.
data = {}
for iteration in series.read_iterations():
    print("Current iteration {}".format(iteration.iteration_index))
    electronPositions = iteration.particles["electrons"]["position"]
    loadedChunks = []
    shapes = []
    dimensions = ["x", "y", "z"]

    for i in range(3):
        dim = dimensions[i]
        rc = electronPositions[dim]
        loadedChunks.append(rc.load_chunk([0], rc.shape))
        shapes.append(rc.shape)

    # Closing the iteration loads all data and releases the current
    # streaming step.
    # If the iteration is not closed, it will be implicitly closed upon
    # opening the next iteration.
    iteration.close()

    # data is now available for printing
    for i in range(3):
        dim = dimensions[i]
        shape = shapes[i]
        print("dim: {}, shape: {}".format(dim, shape))
        chunk = loadedChunks[i]
        data[dim] = chunk  # JArray(JFloat)(chunk)


class OpenPMDVisualiser:

    def __init__(self):
        self.dataToWorldScale = 50000.0

        self.sceneryApp = SceneryBase("OpenPMD visualiser", 1280, 720, True, None)
        self.scene = self.sceneryApp.getScene()
        self.hub = self.sceneryApp.getHub()
        self.settings = self.sceneryApp.getSettings()
        self.hub.add(SceneryElement.Settings, self.settings)
        self.applicationName = self.sceneryApp.getApplicationName()
        self.windowWidth = self.sceneryApp.getWindowWidth()
        self.windowHeight = self.sceneryApp.getWindowHeight()

        self.cam = DetachedHeadCamera()
        self.cam.perspectiveCamera(50.0, self.windowWidth, self.windowHeight, 0.1, 1000.0)
        self.cam.spatial().setPosition(Vector3f(0.0, 0.0, 5.0))
        self.scene.addChild(self.cam)

    def setupLighting(self, spread, radius):
        positions = [
            Vector3f(1.0, 0, -1.0 / sqrt(2.0)).mul(spread),
            Vector3f(-1.0, 0, -1.0 / sqrt(2.0)).mul(spread),
            Vector3f(0.0, 1.0, 1.0 / sqrt(2.0)).mul(spread),
            Vector3f(0.0, -1.0, 1.0 / sqrt(2.0)).mul(spread)
        ]

        for p in positions:
            light = PointLight(radius)
            light.setIntensity(5.0)
            light.setEmissionColor(Random.random3DVectorFromRange(0.2, 0.9))
            light.spatial().setPosition(p)
            self.scene.addChild(light)

    def main(self):
        logging.info("Launching scenery main")
        self.sceneryApp.main()

    def createInstancedNodes(self):
        template = Box(Vector3f(0.001), insideNormals=False)
        template.setMaterial(ShaderMaterial.fromFiles("DefaultDeferredInstanced.vert", "DefaultDeferred.frag"))

        master = InstancedNode(template, "Particle Template")
        self.scene.addChild(master)

        return master

    def loadParticleData(self, x, y, z, node,):

        for i in range(len(x)):
            instance = node.addInstance()
            instance.spatial().setPosition(
                Vector3f(x[i] * self.dataToWorldScale,
                         y[i] * self.dataToWorldScale,
                         z[i] * self.dataToWorldScale))

        print("Added {} particles to scene".format(x.size))

def sceneryApplication():
    app = OpenPMDVisualiser()
    app.setupLighting(10.0, 50.0)
    master = app.createInstancedNodes()
    print("Loading particle data from OpenPMD... ")
    app.loadParticleData(data['x'], data['y'], data['z'], master)
    app.main()


jpype.setupGuiEnvironment(sceneryApplication)
