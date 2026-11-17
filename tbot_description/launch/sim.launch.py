import os

import xacro
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, RegisterEventHandler
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    pkg = get_package_share_directory('tbot_description')
    robot_description = xacro.process_file(
        os.path.join(pkg, 'urdf', 'robot.urdf.xacro')).toxml()

    # 1. Robot model + TF (now using simulation time)
    rsp = Node(package='robot_state_publisher', executable='robot_state_publisher',
               parameters=[{'robot_description': robot_description, 'use_sim_time': True}])

    # 2. Start Gazebo with an empty world (-r = start running immediately)
    world = os.path.join(pkg, 'worlds', 'room.sdf')
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(
            get_package_share_directory('ros_gz_sim'), 'launch', 'gz_sim.launch.py')),
        launch_arguments={'gz_args': f'-r {world}'}.items())

    # 3. Spawn the robot from the /robot_description topic, 5 cm above the ground
    spawn = Node(package='ros_gz_sim', executable='create',
                 arguments=['-topic', 'robot_description', '-name', 'tbot', '-z', '0.05'],
                 output='screen')

    # 4. Bridge Gazebo's clock to ROS (so all nodes share simulation time)
    bridge = Node(package='ros_gz_bridge', executable='parameter_bridge',
                  arguments=[
                      '/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock',
                      '/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan',
                      '/camera/image_raw@sensor_msgs/msg/Image[gz.msgs.Image',
                      '/camera/camera_info@sensor_msgs/msg/CameraInfo[gz.msgs.CameraInfo',
                  ],
                  output='screen')

    # 5. Start the controllers, but only AFTER the robot exists in Gazebo
    jsb = Node(package='controller_manager', executable='spawner',
               arguments=['joint_state_broadcaster'])
    diff = Node(package='controller_manager', executable='spawner',
                arguments=['diff_drive_controller'])

    return LaunchDescription([
        rsp, gazebo, spawn, bridge,
        RegisterEventHandler(OnProcessExit(target_action=spawn, on_exit=[jsb, diff])),
    ])