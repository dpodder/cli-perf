About this repo
===============

The cli-perf repo contains tools to monitor the performance of the [dotnet/cli
repo](https://github.com/dotnet/cli).

Setup Steps
===========

0. Install Visual Studio 2015 (required for the CLI build; the Community Edition
   is good enough)
1. Create a base directory (example here; you can put it anywhere)
       mkdir C:\DotNet
       cd /d C:\DotNet
2. Clone this repo
       git clone https://github.com/dpodder/cli-perf.git
3. Install chocolatey (must run elevated):
       @powershell -NoProfile -ExecutionPolicy Bypass -Command "iex ((new-object net.webclient).DownloadString('https://chocolatey.org/install.ps1'))" && SET PATH=%PATH%;%ALLUSERSPROFILE%\chocolatey\bin
4. Install required tools (must run elevated):
       choco install git -y
       choco install python2 -y
       choco install microsoft-build-tools -y
       choco install cmake.portable -y
       setx /m PATH "%PATH%;C:\Program Files (x86)\MSBuild\14.0\Bin"
5. Launch the rolling script (assuming `C:\DotNet` is the base directory):
       cd /d C:\DotNet\cli-perf\rolling-perf
       py rolling-perf.py --branch rel/1.0.0 --dir C:\DotNet\working-dir
