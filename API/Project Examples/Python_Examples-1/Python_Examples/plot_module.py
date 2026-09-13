import matplotlib.pyplot as plt
import numpy as np

exit_flag = False

def handle_close(evt):
    global exit_flag
    print("Figure closed. Exiting...")
    exit_flag = True

def start_plot(Sup_title="Mode", Subplot1_X=None, Subplot1_Y=None,
               xlabel1="Other Value", ylabel1="Other Value", title1="Subplot 1",
               Subplot2_X=None, I_Data=None, Q_Data=None, 
               xlabel2="Other Value", ylabel2="Other Value", title2="Subplot 2"):

    global exit_flag
    exit_flag = False
    # Determine whether it's a single or dual plot
    is_dual = I_Data is not None
    if is_dual:
        fig, axes = plt.subplots(2, 1, figsize=(10, 6))
    else:
        fig, axes = plt.subplots(1, 1, figsize=(10, 6))
        if not isinstance(axes, (list, tuple)):
            axes = [axes]

    fig.suptitle(Sup_title)

    # First plot:
    if Subplot1_X is None:
        x1 = list(range(len(Subplot1_Y)))
    else:
        x1 = Subplot1_X
    
    line1, = axes[0].plot(x1, Subplot1_Y if Subplot1_Y is not None else [], label=title1)

    axes[0].set_xlabel(xlabel1)
    axes[0].set_ylabel(ylabel1)
    axes[0].set_title(title1)
    axes[0].set_ylim(-160, 25)
    axes[0].legend()

    lines = [line1]

    data_source_y1 = Subplot1_Y 

    # Second plot (if any)
    if len(axes) == 2:
        x2 = Subplot2_X if Subplot2_X is not None else list(range(len(I_Data)))
        line2_1, = axes[1].plot(x2, I_Data, label="I_Data")
        line2_2, = axes[1].plot(x2, Q_Data, label="Q_Data")
        axes[1].set_xlabel(xlabel2)
        axes[1].set_ylabel(ylabel2)
        axes[1].set_title(title2)
        axes[1].autoscale_view()
        axes[1].legend(loc='upper right')
        lines.extend([line2_1, line2_2])

    fig.canvas.mpl_connect('close_event', handle_close)

    plt.ion()
    plt.tight_layout()
    plt.show()

    def update():
        if exit_flag:
            return False
        
        try:
            if data_source_y1 is not None:
                lines[0].set_ydata(data_source_y1)
                axes[0].relim()
                axes[0].autoscale_view()
            
            if len(lines) == 3:

                lines[1].set_ydata(I_Data)
                lines[2].set_ydata(Q_Data)
                axes[1].relim()
                axes[1].autoscale_view()

            plt.draw()
            plt.pause(0.001)
            return True
        except Exception as e:
            print(f"Plot update error: {e}")
            return False
        
    return update

