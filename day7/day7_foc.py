import numpy as np
import matplotlib.pyplot as plt


def clarke_transform(current_a, current_b, current_c):
    alpha = current_a
    beta = (current_a + 2.0 * current_b) / np.sqrt(3.0)
    return alpha, beta


def park_transform(alpha, beta, electrical_angle):
    cos_theta = np.cos(electrical_angle)
    sin_theta = np.sin(electrical_angle)

    d_axis = alpha * cos_theta + beta * sin_theta
    q_axis = -alpha * sin_theta + beta * cos_theta
    return d_axis, q_axis


def inverse_park_transform(d_axis, q_axis, electrical_angle):
    cos_theta = np.cos(electrical_angle)
    sin_theta = np.sin(electrical_angle)

    alpha = d_axis * cos_theta - q_axis * sin_theta
    beta = d_axis * sin_theta + q_axis * cos_theta
    return alpha, beta


def inverse_clarke_transform(alpha, beta):
    current_a = alpha
    current_b = (-alpha + np.sqrt(3.0) * beta) / 2.0
    current_c = (-alpha - np.sqrt(3.0) * beta) / 2.0
    return current_a, current_b, current_c

class PIController:
    def __init__(self, kp, ki, dt, limit):
        self.kp = kp
        self.ki = ki
        self.dt = dt
        self.limit = limit
        self.integral = 0.0

    def step(self, reference, measurement):
        error = reference - measurement
        candidate_integral = np.clip(
            self.integral + error * self.dt,
            -self.limit,
            self.limit,
        )

        raw_output = self.kp * error + self.ki * candidate_integral
        output = np.clip(raw_output, -self.limit, self.limit)

        if output == raw_output:
            self.integral = candidate_integral

        return output


class MotorPlant:
    def __init__(self, inertia=0.02, damping=0.05, dt=0.001):
        self.inertia = inertia
        self.damping = damping
        self.dt = dt
        self.speed = 0.0
        self.angle = 0.0

    def step(self, torque, load_torque):
        acceleration = (
            torque - load_torque - self.damping * self.speed
        ) / self.inertia

        self.speed += acceleration * self.dt
        self.angle += self.speed * self.dt
        return self.speed


def simulate_direct_pid(duration=2.0, dt=0.001):
    time = np.arange(0.0, duration, dt)
    controller = PIController(kp=0.08, ki=0.5, dt=dt, limit=10.0)
    motor = MotorPlant(dt=dt)

    reference_speed = 100.0
    applied_torque = 0.0
    speeds = []
    torques = []

    for current_time in time:
        load_torque = 2.0 if current_time >= 0.8 else 0.0

        torque_command = controller.step(reference_speed, motor.speed)

        # A conventional actuator is modeled with a slower torque response.
        applied_torque += (
            torque_command - applied_torque
        ) * dt / 0.04

        speeds.append(motor.step(applied_torque, load_torque))
        torques.append(applied_torque)

    return time, np.array(speeds), np.array(torques)


def simulate_foc(duration=2.0, dt=0.001):
    time = np.arange(0.0, duration, dt)
    speed_controller = PIController(kp=0.8, ki=5.0, dt=dt, limit=100.0)
    motor = MotorPlant(dt=dt)

    reference_speed = 100.0
    torque_constant = 0.1
    electrical_angle = 0.0
    d_current = 0.0
    q_current = 0.0
    speeds = []
    torques = []

    for current_time in time:
        load_torque = 2.0 if current_time >= 0.8 else 0.0

        d_current_reference = 0.0
        q_current_reference = speed_controller.step(
            reference_speed,
            motor.speed,
        )

        # Fast inner current loop: d-axis controls flux, q-axis controls torque.
        d_current += (d_current_reference - d_current) * dt / 0.005
        q_current += (q_current_reference - q_current) * dt / 0.005

        electrical_angle = 4.0 * motor.angle

        alpha, beta = inverse_park_transform(
            d_current,
            q_current,
            electrical_angle,
        )
        current_a, current_b, current_c = inverse_clarke_transform(
            alpha,
            beta,
        )

        alpha_feedback, beta_feedback = clarke_transform(
            current_a,
            current_b,
            current_c,
        )
        _, q_current_feedback = park_transform(
            alpha_feedback,
            beta_feedback,
            electrical_angle,
        )

        torque = torque_constant * q_current_feedback

        speeds.append(motor.step(torque, load_torque))
        torques.append(torque)

    return time, np.array(speeds), np.array(torques)


time_pid, speed_pid, torque_pid = simulate_direct_pid()
time_foc, speed_foc, torque_foc = simulate_foc()

figure, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

axes[0].plot(time_pid, speed_pid, label="Direct PID speed control")
axes[0].plot(time_foc, speed_foc, label="FOC speed control")
axes[0].axhline(100.0, color="r", linestyle="--", label="speed reference")
axes[0].axvline(0.8, color="gray", linestyle=":", label="load step")
axes[0].set_title("PID vs simplified FOC speed response")
axes[0].set_ylabel("speed")
axes[0].grid(True, alpha=0.3)
axes[0].legend()

axes[1].plot(time_pid, torque_pid, label="Direct PID torque")
axes[1].plot(time_foc, torque_foc, label="FOC q-axis torque")
axes[1].axvline(0.8, color="gray", linestyle=":", label="load step")
axes[1].set_xlabel("time (s)")
axes[1].set_ylabel("torque")
axes[1].grid(True, alpha=0.3)
axes[1].legend()

figure.tight_layout()
figure.savefig("foc_vs_pid.png", dpi=150)

print("Saved: foc_vs_pid.png")