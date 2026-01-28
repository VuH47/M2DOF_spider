# @file
#  @Roboticstoolbox,RV3 from PeterCorke
#  @Vu H

"""
Demo: gait 2DOF.
offsets, and drive the 2-DOF legs via the existing inverse kinematics in the define model.
"""

import time
import numpy as np
import matplotlib.pyplot as plt
from math import pi
from roboticstoolbox import mstraj
from spiquad import *
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


# Gait param
STEP_LENGTH = 0.06  # peak-to-peak
STEP_HEIGHT = 0.04  # lift height
Z_DOWN = 0.0        # ground contact offset (relative to homepos)
Z_UP = STEP_HEIGHT  # swing height

# Timing (seconds) for each segment of the rectangular path
T_SEGMENTS = [0.6, 0.1, 0.2, 0.1]  # stance forward, raise, swing forward, lower
DT = 0.01
TACC = 0.05

#leg phase offsets for a trot (FR/BL are 180° out of phase with FL/BR)
LEG_PHASE_OFFSETS = {"FL": 0.0,"BR": 0.0,"FR": 0.5,"BL": 0.5,}


def build_foot_cycle(step_length=STEP_LENGTH, z_down=Z_DOWN, z_up=Z_UP): #cyclic rec foot path using mstraj

    xf = step_length / 2.0
    xb = -xf

    # Rectangular loop: stance (xf->xb at ground), lift, swing forward, lower
    segments = np.array([[xf, 0.0, z_down],[xb, 0.0, z_down],[xb, 0.0, z_up],[xf, 0.0, z_up],[xf, 0.0, z_down],])
    traj = mstraj(segments, tsegment=T_SEGMENTS, dt=DT, tacc=TACC)
    cycle = traj.q
    cycle = np.vstack((cycle, cycle[-3:, :]))
    return cycle
FOOT_CYCLE = build_foot_cycle()
CYCLE_LEN = FOOT_CYCLE.shape[0]


def get_cycle_index(phase: float) -> int:
    return int((phase % 1.0) * CYCLE_LEN) % CYCLE_LEN


def get_joint_config_from_cycle(robot: QuadrupedRobot, phase: float):
    """
    Compute an 8x1 joint vector using the precomputed foot cycle and leg phase offsets.
    """
    q = []
    for name in robot.leg_names:
        p_leg = (phase + LEG_PHASE_OFFSETS[name]) % 1.0
        idx = get_cycle_index(p_leg)
        dx, dy, dz = FOOT_CYCLE[idx]

        neutral = robot.default_foot_positions[name]
        foot = neutral + np.array([dx, dy, dz])

        t1, t2 = robot.inverse_kinematics(foot[0], foot[1], foot[2])
        q.extend([t1, t2])

    return np.array(q)


def visualize_gait():
    plt.close("all")
    robot = QuadrupedRobot()
    workspace = [-0.15, 0.15, -0.15, 0.15, 0.0, 0.20]
    fig = plt.figure(figsize=(12, 10))
    ax = fig.add_subplot(111, projection="3d")
    ax.set_xlim(workspace[0], workspace[1])
    ax.set_ylim(workspace[2], workspace[3])
    ax.set_zlim(workspace[4], workspace[5])
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_zlabel("Z (m)")
    ax.set_title("Quadruped Robot - apply Gait")

    body_corners = np.array(
        [
            [BODY_SIZE / 2, BODY_SIZE / 2, 0.10],
            [BODY_SIZE / 2, -BODY_SIZE / 2, 0.10],
            [-BODY_SIZE / 2, -BODY_SIZE / 2, 0.10],
            [-BODY_SIZE / 2, BODY_SIZE / 2, 0.10],
            [BODY_SIZE / 2, BODY_SIZE / 2, 0.10],
        ]
    )

    body_line, = ax.plot(
        body_corners[:, 0],
        body_corners[:, 1],
        body_corners[:, 2],
        "k-",
        linewidth=4,
        label="Body",
        zorder=5,
    )



    poly = Poly3DCollection([body_corners[:4]], alpha=0.3, facecolor="cyan", edgecolor="black")
    ax.add_collection3d(poly)
    leg_colors = {"FL": "red", "FR": "blue", "BL": "green", "BR": "orange"}
    leg_plots = {}
    hip_plots = {}
    foot_plots = {}

    # Initialize plots
    q0 = get_joint_config_from_cycle(robot, 0.0)
    for i, name in enumerate(robot.leg_names):
        q_leg = np.array([q0[i * 2], q0[i * 2 + 1]])
        base_pos = robot.leg_positions[name]
        positions = robot.forward_kinematics(q_leg[0], q_leg[1], base_pos)
        line, = ax.plot(positions[:, 0],positions[:, 1],positions[:, 2],color=leg_colors[name],linewidth=5,alpha=0.9,label=f"Leg {name}",zorder=10,)
        leg_plots[name] = line

        hip, = ax.plot([positions[1, 0]],[positions[1, 1]],[positions[1, 2]],"o",color="orange",markersize=12,markeredgecolor="black",markeredgewidth=2,zorder=11,)
        hip_plots[name] = hip

        foot, = ax.plot([positions[2, 0]],[positions[2, 1]],[positions[2, 2]],"o",color="black",markersize=10,markeredgecolor=leg_colors[name],markeredgewidth=3,zorder=11,)
        foot_plots[name] = foot

    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)
    phase = 0.0
    try:
        while True:
            q = get_joint_config_from_cycle(robot, phase)

            for i, name in enumerate(robot.leg_names):
                q_leg = np.array([q[i * 2], q[i * 2 + 1]])
                base_pos = robot.leg_positions[name]
                positions = robot.forward_kinematics(q_leg[0], q_leg[1], base_pos)

                leg_plots[name].set_data(positions[:, 0], positions[:, 1])
                leg_plots[name].set_3d_properties(positions[:, 2])

                hip_plots[name].set_data([positions[1, 0]], [positions[1, 1]])
                hip_plots[name].set_3d_properties([positions[1, 2]])

                foot_plots[name].set_data([positions[2, 0]], [positions[2, 1]])
                foot_plots[name].set_3d_properties([positions[2, 2]])

            ax.set_title(f"Quadruped Robot - Walking.py-style Gait (Phase: {phase % 1.0:.2f})")
            fig.canvas.draw()
            fig.canvas.flush_events()
            plt.pause(0.001)
            phase = (phase + DT / sum(T_SEGMENTS)) % 1.0
            time.sleep(0.02)

    except KeyboardInterrupt:
        plt.close("all")


if __name__ == "__main__":
    print("Gait DEMO animating....")
    visualize_gait()

