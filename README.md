About this repo
===============

The cli-perf repo contains tools to monitor the performance of the [dotnet/cli
repo](https://github.com/dotnet/cli).

Setup Steps
===========

0. Install Visual Studio 2015 (required for the CLI build; the Community Edition
   is good enough)

1. Install chocolatey (must run elevated):

    ```batch
    cd /d %USERPROFILE%
    @powershell -NoProfile -ExecutionPolicy Bypass -Command "iex ((new-object net.webclient).DownloadString('https://chocolatey.org/install.ps1'))" && SET PATH=%PATH%;%ALLUSERSPROFILE%\chocolatey\bin
    ```

2. Install required tools (must run elevated; best to start a clean shell):

    ```batch
    cd /d %USERPROFILE%
    choco install git python2 python microsoft-build-tools cmake.portable -y
    ```

3. Set up dependencies (must run elevated; best to start a clean shell):

    ```batch
    cd /d %USERPROFILE%
    setx /m PATH "%PATH%;C:\Program Files (x86)\MSBuild\14.0\Bin"
    ```

4. Create a base directory--example only here, `C:\DotNet` can be replaced with
   any other path on the system. (Best to start this from a clean,
   *non*-elevated shell.)

    ```batch
    mkdir C:\DotNet
    cd /d C:\DotNet
    ```

5. Clone this repo

    ```batch
    git clone https://github.com/dpodder/cli-perf.git
    ```

Running the Script
==================

```batch
cd /d C:\DotNet\cli-perf\rolling-perf
py rolling-perf.py --branch rel/1.0.0 --dir C:\DotNet\working-dir
```
