# @file
#  @Roboticstoolbox,RV3 from PeterCorke
#  @Vu H


import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
from roboticstoolbox import DHLink, DHRobot
from math import pi
import time

# Robot dimensions
BODY_SIZE = 0.07  #body
THIGH_LENGTH = 0.037  # 3.7 cm (a1)
LEG_LENGTH = 0.052  # 5.2 cm (a2)

class QuadrupedRobot:
    def __init__(self):
        self.a1 = THIGH_LENGTH
        self.a2 = LEG_LENGTH
        self.body_size = BODY_SIZE

        # Create 4 separate 2-DOF leg robots
        self.legs = {}
        self.leg_names = ['FL', 'FR', 'BL', 'BR']

        # Define leg base positions on body 
        self.leg_positions = {
            'FL': np.array([BODY_SIZE/2, BODY_SIZE/2, 0.10]),    # Front Left
            'FR': np.array([BODY_SIZE/2, -BODY_SIZE/2, 0.10]),  
            'BL': np.array([-BODY_SIZE/2, BODY_SIZE/2, 0.10]),   # Back Left
            'BR': np.array([-BODY_SIZE/2, -BODY_SIZE/2, 0.10]),  
        }

        # Default standing position for each leg endpoint  - symmetric 
        self.default_foot_positions = {
            'FL': np.array([0.03, 0.03, -0.10]),    # Front Left: +x, +y
            'FR': np.array([0.03, -0.03, -0.10]),   # mirror y
            'BL': np.array([-0.03, 0.03, -0.10]),   # mirror x
            'BR': np.array([-0.03, -0.03, -0.10]),  # mirror both
        }


        for name in self.leg_names:
            self.legs[name] = self.create_leg(name)

    def create_leg(self, name):
        """
        Create a 2-DOF leg w DH parameters.
        """
        # Hip - revolute, rotates in XY plane
        l1 = DHLink(d=0, a=self.a1, alpha=0, offset=0, qlim=[-pi, pi])

        # Knee- revolute, rotates to extend leg downward
        l2 = DHLink(d=0, a=self.a2, alpha=0, offset=0, qlim=[-pi, pi])
        leg = DHRobot([l1, l2], name=f'Leg_{name}')
        base_pos = self.leg_positions[name]
        leg.base = np.array([[1, 0, 0, base_pos[0]],[0, 1, 0, base_pos[1]],[0, 0, 1, base_pos[2]],[0, 0, 0, 1]])
        return leg

    def foward_kinematic(self, t1, t2, base_pos):
        """
        Calculate positions of joints and foot given joint angles.
        Args:
            t1: Hip joint angle
            t2: Knee joint angle
            base_pos: Base position of the leg (on body)

        Returns:
            positions: Array of [base, hip, foot] positions
        """
        p0 = base_pos
        # Hip joint position (end of thigh)
        p1 = p0 + np.array([self.a1 * np.cos(t1),self.a1 * np.sin(t1),0])
        # Foot position (end of leg)
        # The knee angle t2 is relative to the horizontal plane
        p2 = p1 + np.array([self.a2 * np.cos(t1) * np.cos(t2),self.a2 * np.sin(t1) * np.cos(t2),self.a2 * np.sin(t2)])
        return np.array([p0, p1, p2])

    def inverse_kinematics(self, x, y, z):
        """
        Calculate joint angles using inverse kinematics.
        Args:
            x, y, z: Endpoint coordinates in leg frame

        Returns:
            t1: Hip joint angle (radians)
            t2: Knee joint angle (radians)
        """
        #  t1 = atan2(y, x)
        t1 = np.arctan2(y, x)
        #  t2 = atan2(z, sqrt(x² + y²) - a1)
        r = np.sqrt(x**2 + y**2)
        t2 = np.arctan2(z, r - self.a1)
        return t1, t2

    def get_joint_config(self, phase):
        """
        Get joint configuration for all legs at given gait phase.

        Returns:
            q: 8x1 array of joint angles [FL_hip, FL_knee, FR_hip, FR_knee, ...]
        """
        step_height = 0.04  
        step_length = 0.03 

        # Determine which step (A-F)
        step = int(phase * 6) % 6
        sub_phase = (phase * 6) % 1

        # Default foot positions (standing) - symmetric positions
        foot_positions = {}
        for name in self.leg_names:
            foot_positions[name] = self.default_foot_positions[name].copy()

        # Apply gait pattern
        if step == 0:  # Step A - all on ground
            pass

        elif step == 1:  # Step B - lift FR and BL
            foot_positions['FR'][2] += step_height * sub_phase
            foot_positions['BL'][2] += step_height * sub_phase

        elif step == 2:  # Step C - move FR and BL forward
            foot_positions['FR'][2] += step_height
            foot_positions['BL'][2] += step_height
            foot_positions['FR'][0] += step_length * sub_phase
            foot_positions['BL'][0] += step_length * sub_phase
            foot_positions['FL'][0] -= step_length * 0.5 * sub_phase
            foot_positions['BR'][0] -= step_length * 0.5 * sub_phase

        elif step == 3:  # Step D - lower FR/BL, lift FL/BR
            foot_positions['FR'][2] += step_height * (1 - sub_phase)
            foot_positions['BL'][2] += step_height * (1 - sub_phase)
            foot_positions['FR'][0] += step_length
            foot_positions['BL'][0] += step_length
            foot_positions['FL'][2] += step_height * sub_phase
            foot_positions['BR'][2] += step_height * sub_phase
            foot_positions['FL'][0] -= step_length * 0.5
            foot_positions['BR'][0] -= step_length * 0.5

        elif step == 4:  # Step E - move FL/BR forward
            foot_positions['FL'][2] += step_height
            foot_positions['BR'][2] += step_height
            foot_positions['FL'][0] += step_length * sub_phase - step_length * 0.5
            foot_positions['BR'][0] += step_length * sub_phase - step_length * 0.5
            foot_positions['FR'][0] += step_length - step_length * 0.5 * sub_phase
            foot_positions['BL'][0] += step_length - step_length * 0.5 * sub_phase

        elif step == 5:  # Step F - lower all, return to neutral
            foot_positions['FL'][2] += step_height * (1 - sub_phase)
            foot_positions['BR'][2] += step_height * (1 - sub_phase)
            # Blend back to default - symmetric positions
            for name in foot_positions:
                default = self.default_foot_positions[name]
                foot_positions[name] = (1 - sub_phase) * foot_positions[name] + sub_phase * default

        # Calculate joint angles for all legs
        q = []
        for name in self.leg_names:
            foot = foot_positions[name]
            t1, t2 = self.inverse_kinematics(foot[0], foot[1], foot[2])
            q.extend([t1, t2])

        return np.array(q)


def visualize_quadruped():
    plt.close('all')

    robot = QuadrupedRobot()
    # Set workspace limits (feet at z=0, body in positive z)
    workspace = [-0.15, 0.15, -0.15, 0.15, 0, 0.20]
    q0 = robot.get_joint_config(0.0)

    # Create figure and 3D axes
    fig = plt.figure(figsize=(12, 10))
    ax = fig.add_subplot(111, projection='3d')

    # Set up the axes
    ax.set_xlim(workspace[0], workspace[1])
    ax.set_ylim(workspace[2], workspace[3])
    ax.set_zlim(workspace[4], workspace[5])
    ax.set_xlabel('X (m)')
    ax.set_ylabel('Y (m)')
    ax.set_zlabel('Z (m)')
    ax.set_title('Quadruped Robot - Walking Gait')

    # Body platform corners (body at z=0.10 so feet touch z=0)
    body_corners = np.array([
        [BODY_SIZE/2, BODY_SIZE/2, 0.10],
        [BODY_SIZE/2, -BODY_SIZE/2, 0.10],
        [-BODY_SIZE/2, -BODY_SIZE/2, 0.10],
        [-BODY_SIZE/2, BODY_SIZE/2, 0.10],
        [BODY_SIZE/2, BODY_SIZE/2, 0.10]  # Close the square
    ])

    # Initialize body plot
    body_line, = ax.plot(body_corners[:, 0], body_corners[:, 1], body_corners[:, 2],'k-', linewidth=4, label='Body', zorder=5)

    # Fill body
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    vertices = [body_corners[:4]]
    poly = Poly3DCollection(vertices, alpha=0.3, facecolor='cyan', edgecolor='black')
    ax.add_collection3d(poly)

    # Colors for each leg
    leg_colors = {'FL': 'red', 'FR': 'blue', 'BL': 'green', 'BR': 'orange'}
    leg_plots = {}
    hip_plots = {}
    # foot_plots = {}

    # Plot 
    print("Plotting 4 legs with body...")
    for i, name in enumerate(robot.leg_names):
        q_leg = np.array([q0[i*2], q0[i*2+1]])

        # Get positions using custom forward kinematics
        base_pos = robot.leg_positions[name]
        positions = robot.foward_kinematic(q_leg[0], q_leg[1], base_pos)
        line, = ax.plot(positions[:, 0], positions[:, 1], positions[:, 2],
                       color=leg_colors[name], linewidth=5, alpha=0.9,
                       label=f'Leg {name}', zorder=10)
        leg_plots[name] = line

        # Plot hip joint (orange circle)
        hip, = ax.plot([positions[1, 0]], [positions[1, 1]], [positions[1, 2]],
                      'o', color='orange', markersize=12,
                      markeredgecolor='black', markeredgewidth=2, zorder=11)
        hip_plots[name] = hip

    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)
    print("\nAnimating walking gait...")
    print("Press Ctrl+C to stop\n")
    # Animate the walking 
    phase = 0.0
    step_names = ['A', 'B', 'C', 'D', 'E', 'F']

    try:
        while True:
            # Get joint configuration for current phase
            q = robot.get_joint_config(phase)

            # Update
            for i, name in enumerate(robot.leg_names):
                q_leg = np.array([q[i*2], q[i*2+1]])
                base_pos = robot.leg_positions[name]
                positions = robot.foward_kinematic(q_leg[0], q_leg[1], base_pos)
                leg_plots[name].set_data(positions[:, 0], positions[:, 1])
                leg_plots[name].set_3d_properties(positions[:, 2])
                hip_plots[name].set_data([positions[1, 0]], [positions[1, 1]])
                hip_plots[name].set_3d_properties([positions[1, 2]])

            # Update title with current step
            step_idx = int(phase * 6) % 6
            ax.set_title(f'Quadruped Robot - Step {step_names[step_idx]} (Phase: {phase:.2f})')
            fig.canvas.draw()
            fig.canvas.flush_events()
            plt.pause(0.001)
            print(f"\rStep {step_names[step_idx]} | Phase: {phase:.2f}", end='', flush=True)

            # Increment phase
            phase += 0.04
            if phase >= 5.0:
                phase = 0.0
                print()  # New line after each cycle

            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n\nAnimation stopped.")
        plt.close('all')

if __name__ == '__main__':
    visualize_quadruped()

