# Calculate SNR, THD and range of test sinewaves recorded by an ADC

import matplotlib.pyplot as plt
import csv
import numpy as np
import scipy.signal
import sys

def movingaverage(interval, window_size):
    window= np.ones(int(window_size))/float(window_size)
    return np.convolve(interval, window, 'same')

# paths for file operations

# path = "C:/work/Ommo/Projects/ASIC/Testing/PGA tests/New Tests/16x/"
# config = "65mVac-600mVdc"

path = "D:/prj_noiseanalysis/32x_txt/"
config = "35mVac-600mVdc"

x_file_name = config + ".txt"
x_path = path + x_file_name
channel_sel = 'y'
#plot_path1 = main_path + config + "_Ext_IMU_time.png"
plot_path2 = path + 'plots/' + config + "_" + channel_sel + "_Spectrum.png"
plot_path3 = path + 'plots/' + config + "_" + channel_sel + "_Waveform.png"

spec_filt = []
spec_filt_x = []
spec_filt_y = []
spec_filt_z = []

# constants
fs = 3676.5

# get raw ADC data from text file
#sample_num1 = 0
with open(x_path, 'r') as csvfile:
    datafile = csv.reader(csvfile, delimiter = '\t')
    for row in datafile:
        spec_filt_x.append(float(row[0]))  
        spec_filt_y.append(float(row[1]))  
        spec_filt_z.append(float(row[2]))  
    
# select raw data source from X/Y/Z ADC data
if (channel_sel == 'x'):
    spec_filt = spec_filt_x
if (channel_sel == 'y'):
    spec_filt = spec_filt_y    
if (channel_sel == 'z'):
    spec_filt = spec_filt_z
    
# apply Walch power function to raw ADC data set     
fft_len = 1024 * 32
xF, spectrum = scipy.signal.welch(spec_filt, fs=fs, nperseg=fft_len, noverlap=0)       
scaled_values = spectrum
freq_resp = 10*(np.log10(scaled_values))
end_freq = 1000

# limit BW to 1000 Hz
limited_freqs = [x for x in xF if x < end_freq] # limit frequencies only upto 1000 Hz
limited_dB = freq_resp[:len(limited_freqs)]     # limit corresponding dB values
limited_dB[0] = 0
max_dB = round(max(limited_dB),1)
min_dB = round(min(limited_dB),1)
f_peak_pos = np.argmax(limited_dB)
f_peak = limited_freqs[f_peak_pos]
if((max_dB < 30) or (f_peak < 5) or (f_peak > 120)):
    print("***No Valid Excitation Signal Found***")
    sys.exit()

# find peak gain of the harmonics & sub-harmonics and extract THD
max_harm = max(limited_dB[int(f_peak_pos*1.5):len(limited_freqs)])
max_sub_harm = max(limited_dB[9:int(f_peak_pos/1.5)])
THD = round((max_dB - max(max_harm,max_sub_harm)),1)
f_exc = limited_freqs[f_peak_pos]

# estimate noise floor
n_floor = [x for x in xF if x < 1000]
min_f = 60          # expressed as channel number (approx 6 Hz)
max_peak = 0.5        # max dB per channel increment
peak_factor = 20    # used to create a sliding window that grows in length with freq.
n_floor1 = 5 + movingaverage(limited_dB, 20)
i = 0
while i < len(n_floor1):
    if i < min_f:
        n_floor[i] = n_floor1[i]
    else:
        max_floor = max(n_floor1[i:(i + int(i/peak_factor))])
        if  max_floor - n_floor[i-1] > max_peak:
            n_floor[i] = n_floor[i-1]
        else:
            n_floor[i] = max_floor
    i += 1
        
# calculate SNR    
nf = n_floor[f_peak_pos]
SNR = round((max_dB - nf),1) 

# Spectral Plot
graph_top = 10*(round((max_dB/10),0)) + 10
graph_bot = 10*(round((min_dB/10),0)) 
plt.figure(figsize=(12,8), dpi=200)
ax = plt.subplot()
plt.title('PGA Test ' + channel_sel + '_' + config)
ax.plot(limited_freqs, limited_dB, color='black', linewidth=2) # plot raw spectral data
ax.plot(limited_freqs, n_floor, color='red', linewidth=1) # plot raw spectral data
ax.set_xscale('log')
plt.xlabel('Frequency [Hz]')
plt.ylabel('ADC Output Data [dB]')
plt.grid(visible=True, which='both', axis='both')
plt.axis([1, 1000, graph_bot, graph_top])
plt.grid(which='major', color='black', linestyle='-', linewidth = 0.75)
plt.grid(which='minor', color='black', linestyle='-', linewidth = 0.25)
plt.text(1.2, graph_top-8, 'SNR = ' + str(SNR) + ' dB',fontsize=12)
plt.text(1.2, graph_top-15, 'THD = ' + str(THD) + ' dB',fontsize=12)
plt.savefig(plot_path2) 
plt.show()             

# Waveform plot, will display 2 cycles of the input excitation waveform  
# first search for a positive going transition
i = 0 
while (spec_filt[i] > 0 and i < (len(spec_filt)-1)):
    i += 1 
while (spec_filt[i] < 0 and i < (len(spec_filt)-1)):
    i += 1
if (i > 8000):
    i = 0

wave_max = max(spec_filt)  
wave_min = min(spec_filt)

wave_plot_top = wave_max + abs(wave_max * 0.2)
wave_plot_bot = wave_min - abs(wave_min * 0.2)
range_sine = round(100*((wave_max - wave_min)/float(2**24)),1)
offset = 100*((abs(wave_max) - abs(wave_min))/((wave_max - wave_min)/2))
plot_len = int(round((2*fs/f_exc),0))
plt.figure(figsize=(12,8), dpi=200)
ax = plt.subplot()     
ax.plot(spec_filt[i:(i+plot_len)], color='black', linewidth=2)   
plt.xlabel('Samples [N]')
plt.ylabel('ADC Output Value [K]')  
plt.title('Raw Data: ' + channel_sel + '_' + config) 
plt.grid(which='major', color='black', linestyle='-', linewidth = 0.25) 
plt.axis([0, plot_len, wave_plot_bot, wave_plot_top])
plt.text(int(plot_len/50),(wave_min*0.9), str(range_sine) + '% of FSD',fontsize=12)
plt.text(int(plot_len/50),(wave_min*0.75),'Fin = ' + str(round(f_peak,1)) + ' Hz',fontsize=12)
plt.text(int(plot_len/50),(wave_min*0.60),'Offset = ' + str(round(offset,1)) + '%',fontsize=12)
plt.savefig(plot_path3)
plt.show()        