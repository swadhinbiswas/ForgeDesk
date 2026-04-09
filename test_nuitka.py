import sys
import __main__
print("cwd:", getattr(sys, "frozen", False))
print("main compiled:", hasattr(__main__, "__compiled__"))
print("main file:", getattr(__main__, "__file__", "None"))
print("sys argv[0]:", sys.argv[0])
print("__file__:", __file__)
