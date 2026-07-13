import numpy as np
import matplotlib.pyplot as plt


class PID:
    def __init__(self, kp, ki, kd, dt=0.001, limit=100.0, alpha=0.1):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.dt = dt
        self.limit = limit
        self.alpha = alpha

        self.integral = 0.0
        self.previous_error = 0.0
        self.previous_measurement = 0.0
        self.previous_derivative = 0.0

    def step(self, setpoint, measurement):
        error = setpoint - measurement

        candidate_integral = np.clip(
            self.integral + error * self.dt,
            -self.limit,
            self.limit,
        )

        raw_derivative = -(
        measurement - self.previous_measurement
        ) / self.dt

        derivative = (
            self.alpha * raw_derivative
            + (1.0 - self.alpha) * self.previous_derivative
        )

        raw_output = (
            self.kp * error
            + self.ki * candidate_integral
            + self.kd * derivative
        )
        output = np.clip(raw_output, -self.limit, self.limit)

        # 输出饱和时不继续累积积分项，避免积分饱和。
        if output == raw_output:
            self.integral = candidate_integral

        self.previous_error = error
        self.previous_measurement = measurement
        self.previous_derivative = derivative
        return output
    
class Motor:
    def __init__(self, gain=1.0, time_constant=0.1, dt=0.001):
        self.gain = gain
        self.time_constant = time_constant
        self.dt = dt
        self.position = 0.0

    def step(self, control_output):
        self.position += (
            -self.position / self.time_constant
            + self.gain * control_output / self.time_constant
        ) * self.dt
        return self.position
    
class DelayedMotor(Motor):
    def __init__(self, gain=1.0, time_constant=0.1, dt=0.001, delay=0.02):
        super().__init__(gain, time_constant, dt)

        delay_steps = max(1, round(delay / dt))
        self.command_buffer = [0.0] * delay_steps

    def step(self, control_output):
        self.command_buffer.append(control_output)
        delayed_output = self.command_buffer.pop(0)

        return super().step(delayed_output)
    

    
def simulate(kp, ki, kd, setpoint=1.0, duration=5.0, dt=0.001):
    pid = PID(kp, ki, kd, dt=dt)
    motor = Motor(dt=dt)

    time = np.arange(0.0, duration, dt)
    positions = []
    controls = []

    for _ in time:
        control = pid.step(setpoint, motor.position)
        position = motor.step(control)

        controls.append(control)
        positions.append(position)

    positions = np.array(positions)
    controls = np.array(controls)

    overshoot = max(0.0, (positions.max() - setpoint) / setpoint * 100.0)

    rise_candidates = np.where(positions >= 0.9 * setpoint)[0]
    rise_time = (
        time[rise_candidates[0]]
        if len(rise_candidates) > 0
        else float("inf")
    )

    steady_state_error = np.mean(np.abs(positions[-1000:] - setpoint))

    return time, positions, controls, overshoot, rise_time, steady_state_error

configs = [
    (2.0, 0.5, 0.1, "baseline"),
    (5.0, 0.5, 0.1, "high Kp"),
    (2.0, 2.0, 0.1, "high Ki"),
    (2.0, 0.5, 0.5, "high Kd"),
]

figure, axes = plt.subplots(2, 2, figsize=(12, 8))

for axis, (kp, ki, kd, label) in zip(axes.flat, configs):
    time, positions, controls, overshoot, rise_time, steady_state_error = simulate(
        kp, ki, kd
    )

    axis.plot(time, positions, label="position")
    axis.axhline(1.0, color="r", linestyle="--", label="setpoint")
    axis.set_title(
        f"{label}: overshoot={overshoot:.1f}%, "
        f"rise={rise_time:.3f}s, error={steady_state_error:.4f}"
    )
    axis.set_xlabel("time (s)")
    axis.set_ylabel("position")
    axis.grid(True, alpha=0.3)
    axis.legend()

    print(
        f"{label}: overshoot={overshoot:.2f}%, "
        f"rise_time={rise_time:.3f}s, "
        f"steady_state_error={steady_state_error:.6f}"
    )

figure.suptitle("PID parameter comparison")
figure.tight_layout()
figure.savefig("pid_comparison.png", dpi=150)

print("Saved: pid_comparison.png")

def simulate_proportional(kp, setpoint=1.0, duration=1.0, dt=0.001):
    pid = PID(kp, 0.0, 0.0, dt=dt)
    motor = DelayedMotor(dt=dt, delay=0.02)

    time = np.arange(0.0, duration, dt)
    positions = []

    for _ in time:
        control = pid.step(setpoint, motor.position)
        positions.append(motor.step(control))

    return time, np.array(positions)


test_gains = [7.5, 7.8, 8.0, 8.2]
figure, axes = plt.subplots(2, 2, figsize=(12, 8))

for axis, kp in zip(axes.flat, test_gains):
    time, positions = simulate_proportional(kp)

    axis.plot(time, positions, label=f"Kp={kp}")
    axis.axhline(1.0, color="r", linestyle="--", label="setpoint")
    axis.set_title(f"P-only control: Kp={kp}")
    axis.set_xlabel("time (s)")
    axis.set_ylabel("position")
    axis.grid(True, alpha=0.3)
    axis.legend()

figure.suptitle("Ziegler-Nichols P-only sweep")
figure.tight_layout()
figure.savefig("zn_p_sweep.png", dpi=150)

print("Saved: zn_p_sweep.png")

ku = 8.2
tu = 0.075

zn_kp = 0.6 * ku
zn_ki = 2.0 * zn_kp / tu
zn_kd = zn_kp * tu / 8.0

pid = PID(zn_kp, zn_ki, zn_kd, dt=0.001)
motor = DelayedMotor(dt=0.001, delay=0.02)

time = np.arange(0.0, 2.0, 0.001)
positions = []

for _ in time:
    control = pid.step(1.0, motor.position)
    positions.append(motor.step(control))

positions = np.array(positions)
overshoot = max(0.0, (positions.max() - 1.0) * 100.0)

figure, axis = plt.subplots(figsize=(9, 5))
axis.plot(time, positions, label="ZN PID response")
axis.axhline(1.0, color="r", linestyle="--", label="setpoint")
axis.set_title(
    f"ZN PID: Kp={zn_kp:.2f}, Ki={zn_ki:.2f}, "
    f"Kd={zn_kd:.3f}, overshoot={overshoot:.1f}%"
)
axis.set_xlabel("time (s)")
axis.set_ylabel("position")
axis.grid(True, alpha=0.3)
axis.legend()
figure.tight_layout()
figure.savefig("zn_pid_response.png", dpi=150)

print(
    f"ZN PID: Kp={zn_kp:.2f}, Ki={zn_ki:.2f}, "
    f"Kd={zn_kd:.3f}, overshoot={overshoot:.2f}%"
)
print("Saved: zn_pid_response.png")