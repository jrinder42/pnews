import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
  name='pnews-jrinder42',
  version='0.1.0',
  description=long_description,
  author='Jordan Rinder',
  author_email='jordan.rinder@gmail.com',
  packages=setuptools.find_packages(),
  install_requires=[
    "pyfiglet",
    "typing",
    "toml",
    "feedparser"
  ],
  python_requires='>=3.6',
  license='MIT',
)