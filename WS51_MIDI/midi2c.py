#!/usr/bin/env python3
"""
MIDI -> WS51_MIDI main.c Converter

Usage:
    python midi2c.py <midi_file_path> [options]

Options:
    --bps N        Ticks per second (Default: automatically calculated from MIDI tempo)
    --tracks 1,2,3,4  Specify the track numbers (0-indexed) to map to CH1~CH4
    --list         Only list track information in the MIDI file, do not convert
    --output FILE  Output C file path (Default: overwrite main.c)
    --bps-factor N BPS multiplier (Default: 1.0, higher means higher resolution)

Examples:
    python midi2c.py song.mid --list            # Check available tracks
    python midi2c.py song.mid --tracks 0,1,2,3  # Use the first 4 tracks
    python midi2c.py song.mid --bps 16          # Manually set BPS=16
"""

import sys
import os
import argparse
from collections import defaultdict

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

try:
    import mido
except ImportError:
    print("Error: The 'mido' package is required.")
    print("Please run: pip install mido")
    sys.exit(1)


def midi_note_to_freq(note):
    """MIDI note number -> Frequency (Hz)"""
    if note < 0 or note > 127:
        return 0
    return int(round(440.0 * (2.0 ** ((note - 69) / 12.0))))


def parse_midi_events(midi_file):
    """Parse MIDI file and extract note events (start_tick, end_tick, note, velocity) for each track"""
    mid = mido.MidiFile(midi_file)

    track_events = []  # list of list of (abs_tick, note, velocity, duration_ticks)

    for track_idx, track in enumerate(mid.tracks):
        events = []
        abs_time = 0
        active_notes = {}  # note -> (start_tick, velocity)

        for msg in track:
            abs_time += msg.time

            if msg.type == 'note_on' and msg.velocity > 0:
                active_notes[msg.note] = (abs_time, msg.velocity)
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                if msg.note in active_notes:
                    start_tick, velocity = active_notes.pop(msg.note)
                    events.append((start_tick, msg.note, velocity, abs_time - start_tick))

        # Handle notes that never received a note_off event
        for note, (start_tick, velocity) in active_notes.items():
            events.append((start_tick, note, velocity, abs_time - start_tick))

        track_events.append(events)

    return mid, track_events


def get_track_info(mid, track_events):
    """Get summary information for each track"""
    # Extract track name and instrument
    track_names = [f"Track {i}" for i in range(len(mid.tracks))]
    instruments = ["N/A"] * len(mid.tracks)
    channel_map = ["N/A"] * len(mid.tracks)

    for track_idx, track in enumerate(mid.tracks):
        abs_time = 0
        for msg in track:
            abs_time += msg.time
            if msg.type == 'track_name':
                track_names[track_idx] = msg.name.strip() or track_names[track_idx]
            elif msg.type == 'program_change':
                instruments[track_idx] = f"Program {msg.program}"
            elif msg.type == 'note_on' or msg.type == 'note_off':
                if hasattr(msg, 'channel'):
                    channel_map[track_idx] = f"CH{msg.channel}"

    info = []
    for idx, events in enumerate(track_events):
        notes = sorted(set(e[1] for e in events))
        note_names = [midi_note_name(n) for n in notes[:10]]
        note_preview = ", ".join(note_names)
        if len(notes) > 10:
            note_preview += f"... (+{len(notes) - 10} more)"
        info.append({
            'index': idx,
            'name': track_names[idx],
            'channel': channel_map[idx],
            'instrument': instruments[idx],
            'note_count': len(events),
            'unique_notes': len(notes),
            'notes': notes,
            'note_preview': note_preview,
            'events': events,
        })
    return info


def midi_note_name(note):
    """MIDI number -> Note name (e.g., C4, F#5)"""
    names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    octave = (note // 12) - 1
    name = names[note % 12]
    return f"{name}{octave}"


def build_tempo_map(mid):
    """
    Build tempo map: returns a function to convert ticks to seconds
    and also returns the total duration (seconds)
    """
    ppq = mid.ticks_per_beat
    if ppq is None:
        raise ValueError("MIDI file lacks PPQ (ticks per beat) information; conversion is impossible")

    # Use default tempo first (120 BPM = 500000 us per beat)
    default_tempo = 500000

    # Find all tempo events (in track 0 or any track)
    tempo_events = []  # (tick, tempo_in_us_per_beat)
    for track in mid.tracks:
        abs_time = 0
        for msg in track:
            abs_time += msg.time
            if msg.type == 'set_tempo':
                tempo_events.append((abs_time, msg.tempo))

    tempo_events.sort(key=lambda x: x[0])

    # Find the last tick
    max_tick = 0
    for track in mid.tracks:
        abs_time = 0
        for msg in track:
            abs_time += msg.time
        max_tick = max(max_tick, abs_time)

    # Calculate time for each tick
    def ticks_to_seconds(ticks):
        if not tempo_events:
            return (ticks / ppq) * (default_tempo / 1_000_000.0)

        total_sec = 0.0
        prev_tick = 0
        prev_tempo = default_tempo

        for t, tempo in tempo_events:
            if ticks <= t:
                break
            segment_ticks = t - prev_tick
            total_sec += (segment_ticks / ppq) * (prev_tempo / 1_000_000.0)
            prev_tick = t
            prev_tempo = tempo

        # Remaining part
        if ticks > prev_tick:
            total_sec += ((ticks - prev_tick) / ppq) * (prev_tempo / 1_000_000.0)

        return total_sec

    total_duration = ticks_to_seconds(max_tick)
    return ticks_to_seconds, total_duration, ppq, tempo_events


def generate_c_arrays(track_infos, selected_tracks, bps, total_duration):
    """
    Generate C array data based on selected tracks

    selected_tracks: list of 4 track indices (corresponding to CH1~CH4)
    bps: updates per second
    total_duration: total MIDI duration (seconds)
    """
    fpos = int(total_duration * bps)

    if fpos < 1:
        fpos = 1

    # Collect all unique notes
    all_notes = set()
    for ti in selected_tracks:
        if ti is not None and ti < len(track_infos):
            for event in track_infos[ti]['events']:
                all_notes.add(event[1])

    # TONE_TABLE: index 0 = 0 (silence), followed by each note mapped to a frequency
    # Sort notes from lowest to highest
    sorted_notes = sorted(all_notes)
    tone_table = [0] + [midi_note_to_freq(n) for n in sorted_notes]

    # note -> tone_table index mapping
    note_to_idx = {note: i + 1 for i, note in enumerate(sorted_notes)}
    note_to_idx[None] = 0  # silence

    # Build active notes timeline for each channel
    # channel_timelines[i] = list of (start_sec, end_sec, tone_idx)
    channel_timelines = []

    for ti in selected_tracks:
        timelines = []
        if ti is not None and ti < len(track_infos):
            for start_tick, note, velocity, dur_ticks in track_infos[ti]['events']:
                start_sec = ticks_to_seconds_fn(start_tick)
                end_sec = ticks_to_seconds_fn(start_tick + dur_ticks)
                tone_idx = note_to_idx.get(note, 0)
                timelines.append((start_sec, end_sec, tone_idx))
        channel_timelines.append(timelines)

    # Generate CHnT arrays
    ch_arrays = []
    step_duration = 1.0 / bps

    for ch_idx, timelines in enumerate(channel_timelines):
        arr = []
        for step in range(fpos):
            step_time = step * step_duration
            # Check if there is an active note at this time point
            active_idx = 0  # default: silence
            for start_sec, end_sec, tone_idx in timelines:
                if start_sec <= step_time < end_sec:
                    active_idx = tone_idx
                    break
            arr.append(active_idx)
        ch_arrays.append(arr)

    return {
        'BPS': bps,
        'FPOS': fpos,
        'TONE_TABLE': tone_table,
        'CH1T': ch_arrays[0] if len(ch_arrays) > 0 else [0] * fpos,
        'CH2T': ch_arrays[1] if len(ch_arrays) > 1 else [0] * fpos,
        'CH3T': ch_arrays[2] if len(ch_arrays) > 2 else [0] * fpos,
        'CH4T': ch_arrays[3] if len(ch_arrays) > 3 else [0] * fpos,
    }


def format_c_array(name, values, entry_type="uint16_t", max_per_line=20):
    """Format C array"""
    lines = []
    lines.append(f"const {entry_type} code {name}[] = {{")
    for i in range(0, len(values), max_per_line):
        chunk = values[i:i + max_per_line]
        line = "    " + ", ".join(str(v) for v in chunk) + ","
        lines.append(line)
    lines.append("};")
    lines.append("")
    return "\n".join(lines)


def write_main_c(output_path, data):
    """Write generated data to main.c"""
    original_c = os.path.join(os.path.dirname(os.path.abspath(__file__)), "WS51_MIDI", "main.c")

    if os.path.exists(original_c):
        with open(original_c, 'r', encoding='utf-8') as f:
            content = f.read()
    else:
        print(f"Warning: Original main.c not found ({original_c}), generating a new file")
        content = ""

    import re

    # Update BPS
    content = re.sub(r'#define BPS \d+', f'#define BPS {data["BPS"]}', content)

    # Update FPOS
    content = re.sub(
        r'const uint32_t FPOS = \d+;',
        f'const uint32_t FPOS = {data["FPOS"]};',
        content
    )

    # Update TONE_TABLE
    tone_vals = ", ".join(str(v) for v in data['TONE_TABLE'])
    content = re.sub(
        r'const uint16_t code TONE_TABLE\[\] = \{.*?\};',
        f'const uint16_t code TONE_TABLE[] = {{{tone_vals}}};',
        content,
        flags=re.DOTALL
    )

    # Update CH1T ~ CH4T
    for ch in ['CH1T', 'CH2T', 'CH3T', 'CH4T']:
        vals = ", ".join(str(v) for v in data[ch])
        content = re.sub(
            rf'const char code {ch}\[\] = {{.*?}};',
            f'const char code {ch}[] = {{{vals}}};',
            content,
            flags=re.DOTALL
        )

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Successfully written to: {output_path}")


def main():
    global ticks_to_seconds_fn

    parser = argparse.ArgumentParser(
        description='MIDI -> WS51_MIDI main.c Converter',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python midi2c.py song.mid --list
  python midi2c.py song.mid --tracks 0,1,2,3
  python midi2c.py song.mid --bps 16 --tracks 1,2,3,5
        """
    )
    parser.add_argument('midi_file', nargs='?', help='MIDI file path')
    parser.add_argument('--list', action='store_true', help='List MIDI track information')
    parser.add_argument('--tracks', type=str, default=None, help='Track numbers to map to CH1~CH4 (comma-separated, e.g., 0,1,2,3)')
    parser.add_argument('--bps', type=int, default=None, help='Ticks per second (Default: automatically calculated)')
    parser.add_argument('--pps', type=float, default=None, help='Steps per beat (e.g., --pps 8 = 8 steps per beat)')
    parser.add_argument('--output', type=str, default=None, help='Output file path')
    parser.add_argument('--bps-factor', type=float, default=1.0, help='BPS multiplier adjustment (Default: 1.0)')

    args = parser.parse_args()

    if args.midi_file is None:
        # Try using tkinter file dialog
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            midi_path = filedialog.askopenfilename(
                title="Select MIDI File",
                filetypes=[("MIDI files", "*.mid *.midi"), ("All files", "*.*")]
            )
            root.destroy()
            if not midi_path:
                print("No file selected.")
                sys.exit(0)
        except ImportError:
            parser.print_help()
            print("\nError: Please specify the MIDI file path")
            sys.exit(1)
    else:
        midi_path = args.midi_file

    if not os.path.exists(midi_path):
        print(f"Error: File not found: {midi_path}")
        sys.exit(1)

    print(f"Reading MIDI file: {midi_path}")
    mid, track_events = parse_midi_events(midi_path)
    track_infos = get_track_info(mid, track_events)

    # Build tempo map
    global ticks_to_seconds_fn
    ticks_to_seconds_fn, total_duration, ppq, tempo_events = build_tempo_map(mid)

    print(f"\nMIDI Information:")
    print(f"  PPQ (ticks per beat): {ppq}")
    print(f"  Total Duration: {total_duration:.2f} seconds ({total_duration / 60:.2f} minutes)")
    print(f"  Track Count: {len(mid.tracks)}")
    print(f"  Tempo Changes: {len(tempo_events)}")
    print()

    # List track information
    print(f"{'Idx':<4} {'Track Name':<25} {'Events':<8} {'Unique Notes':<13} {'Channel':<8} {'Notes Preview'}")
    print("-" * 100)
    for info in track_infos:
        print(f"{info['index']:<4} {info['name'][:24]:<25} {info['note_count']:<8} {info['unique_notes']:<13} {info['channel']:<8} {info['note_preview']}")

    if args.list:
        sys.exit(0)

    # Select tracks
    if args.tracks:
        try:
            selected = [int(x.strip()) for x in args.tracks.split(',')]
        except ValueError:
            print("Error: --tracks format is incorrect, should be comma-separated numbers, e.g., 0,1,2,3")
            sys.exit(1)
    else:
        # Interactive selection
        print("\nPlease select 4 tracks to map to CH1~CH4 (enter track numbers, comma-separated):")
        print("Example: 0,1,2,3")
        try:
            selection = input("> ").strip()
            selected = [int(x.strip()) for x in selection.split(',')]
        except (ValueError, EOFError):
            print("Cancelled.")
            sys.exit(0)

    if len(selected) != 4:
        print(f"Warning: 4 tracks are required, but {len(selected)} were received")

    # Ensure there are 4 tracks (pad with None if insufficient)
    while len(selected) < 4:
        selected.append(None)

    selected = selected[:4]

    print(f"\nSelected tracks: CH1={selected[0]}, CH2={selected[1]}, CH3={selected[2]}, CH4={selected[3]}")

    # Process BPS
    if args.pps:
        # Calculate BPM
        bpm = 120.0  # default
        if tempo_events:
            # Use the first tempo
            bpm = 60_000_000.0 / tempo_events[0][1]
        bps = int(round((bpm / 60.0) * args.pps * args.bps_factor))
        print(f"\nSteps per beat {args.pps}, BPM={bpm:.1f} -> BPS={bps}")
    elif args.bps:
        bps = int(round(args.bps * args.bps_factor))
        print(f"\nManual BPS: {bps}")
    else:
        # Automatic calculation: default 4 steps per beat
        bpm = 120.0
        if tempo_events:
            bpm = 60_000_000.0 / tempo_events[0][1]
        bps = int(round((bpm / 60.0) * 4 * args.bps_factor))
        print(f"\nAutomatic BPS (4 steps per beat, BPM={bpm:.1f}): {bps}")

    if bps < 1:
        bps = 1

    # Generate C arrays
    print("\nGenerating C arrays...")
    data = generate_c_arrays(track_infos, selected, bps, total_duration)

    fpos = data['FPOS']
    memory_kb = fpos * 4  # 4 bytes per step (one char per channel)
    print(f"  FPOS (Total steps): {fpos}")
    print(f"  TONE_TABLE length: {len(data['TONE_TABLE'])}")
    print(f"  Each CHnT length: {len(data['CH1T'])}")
    print(f"  Estimated memory usage: ~{memory_kb / 1024:.1f} KB (Flash)")
    print(f"  Flash limit: 16 KB")

    if memory_kb > 14 * 1024:  # Leave 2KB for code
        print(f"  *** Warning: Data is too large, may exceed Flash capacity! Please lower BPS ***")

    # Write to file
    if args.output:
        output_path = args.output
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(script_dir, "WS51_MIDI", "main.c")

    write_main_c(output_path, data)

    # Display summary
    print(f"\n=== Generation Summary ===")
    print(f"BPS: {data['BPS']}")
    print(f"FPOS: {data['FPOS']}")
    print(f"TONE_TABLE: {data['TONE_TABLE']}")
    print(f"\nNote count per channel:")
    for ch_name, ti in zip(['CH1T', 'CH2T', 'CH3T', 'CH4T'], selected):
        if ti is not None and ti < len(track_infos):
            note_count = track_infos[ti]['note_count']
            print(f"  {ch_name} (Track {ti}): {note_count} notes")
        else:
            print(f"  {ch_name}: (No track)")

    # Display first 20 values of CHnT as preview
    for ch_name in ['CH1T', 'CH2T', 'CH3T', 'CH4T']:
        arr = data[ch_name]
        preview = arr[:30]
        print(f"  {ch_name} preview: {preview}{'...' if len(arr) > 30 else ''}")


if __name__ == '__main__':
    main()