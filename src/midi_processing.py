from mido import MidiFile, MidiTrack, Message
import mido
import re
import os


# Function to extract notes from a MIDI track
def extract_notes_from_track(track):
    notes = []
    current_time = 0
    current_note = None

    for msg in track:
        current_time += msg.time

        if msg.type == 'note_on':
            if msg.velocity > 0:
                if current_note is not None:
                    # Append the previous note with its duration
                    notes.append((current_note[0], current_time - current_note[1]))
                # Start a new note
                current_note = (msg.note, current_time)

    return notes


def convert_to_buckets(all_guitar_notes, interval=30, num_buckets=8):
    converted_list = [
        (first, i+1) for first, second in all_guitar_notes
        for i in range(num_buckets) if (i*interval) < second <= ((i+1)*interval)
    ]
    return converted_list


def generate_midi_from_tokens(tokens, ticks_per_beat, output_file_name, subdivision=16):
    """
    Convert a list of tokens back into a MIDI track and save it as a MIDI file.
    
    :param tokens: List of tokens where each token is a note (integer) or None (rest).
    :param ticks_per_beat: The MIDI file's ticks per beat.
    :param subdivision: Number of time steps per beat (must match extraction parameter).
    :param output_path: Path to save the output MIDI file.
    """
    step_size = ticks_per_beat // subdivision

    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname('./output/'), exist_ok=True)

    # Create a new MIDI file and track
    mid = MidiFile(ticks_per_beat=ticks_per_beat)
    track = MidiTrack()
    mid.tracks.append(track)

    current_time = 0  # Current absolute time in ticks
    previous_token = None  # Track the previously active note

    for i, token in enumerate(tokens):
        step_time = i * step_size  # Absolute time for the current step

        if token != previous_token:
            delta_time = step_time - current_time
            events = []

            # Generate note_off for the previous token if it exists
            if previous_token is not None:
                events.append(('note_off', previous_token))

            # Generate note_on for the current token if it exists
            if token is not None:
                events.append(('note_on', token))

            # Add events to the track with appropriate delta times
            for idx, (event_type, note) in enumerate(events):
                # The first event has the computed delta_time, others have 0
                msg_time = delta_time if idx == 0 else 0

                if event_type == 'note_off':
                    msg = Message('note_off', note=note, velocity=0, time=msg_time)
                else:
                    # Use default velocity since original wasn't stored
                    msg = Message('note_on', note=note, velocity=64, time=msg_time)

                track.append(msg)

            # Update the current_time to the current step's time
            current_time = step_time
            previous_token = token

    # Add final note_off if needed
    if previous_token is not None:
        final_time = len(tokens) * step_size
        delta_time = final_time - current_time
        track.append(Message('note_off', note=previous_token, velocity=0, time=delta_time))

    # Save the MIDI file
    mid.save('./output/' + output_file_name)
    return mid


def find_guitar_track(midi_file, track_name='guitar'):
    # Case-insensitive regex pattern for 'guitar'
    tracks = []
    pattern = re.compile(track_name, re.IGNORECASE)
    for track in midi_file.tracks:
        if re.search(pattern, track.name):
            tracks.append(track)
    return tracks


def find_key(midi_file):
    # Iterate over the tracks and extract key information
    current_key = 'unknown'
    for track in midi_file.tracks:
        for message in track:
            if message.type == 'key_signature':
                current_key = message.key
                print(f"At time {message.time}, key signature changed to: {current_key}")

    # If you want to see the final key signature after the whole file has been processed
    print(f"Final key signature: {current_key}")
    return current_key


def process_midi_file(file_path, track_name='guitar', subdivision=16):
    midi_file = mido.MidiFile(file_path)
    guitar_tracks = find_guitar_track(midi_file, track_name)

    all_guitar_notes = []
    if guitar_tracks:
        key = find_key(midi_file)
        for guitar_track in guitar_tracks:
            guitar_notes = extract_tokens_with_granularity(guitar_track,
                                                           midi_file.ticks_per_beat,
                                                           subdivision=subdivision)
            all_guitar_notes.extend(guitar_notes)
    else:
        print(f"No '{track_name}' track found in the MIDI file.")
    return all_guitar_notes, key, midi_file.ticks_per_beat


def extract_tokens_with_granularity(track, ticks_per_beat, subdivision=16):
    """
    Convert a MIDI track into a list of tokens (notes or rests) using fixed time steps.
    
    :param track: List of MIDI messages.
    :param ticks_per_beat: The MIDI file's ticks per beat.
    :param subdivision: Number of time steps per beat (e.g., 16 means each quarter note has 16 steps).
    :return: A list of tokens. A token can be a note (an integer) or None (for a rest).
    """
    step_size = ticks_per_beat // subdivision
    
    # First, create a list of events with their absolute times.
    events = []
    current_time = 0
    for msg in track:
        current_time += msg.time
        events.append((current_time, msg))
        
    # Determine the final time
    final_time = events[-1][0] if events else 0
    
    tokens = []  # This will hold the note tokens at each time step.
    event_index = 0
    active_notes = {}  # Keep track of active notes: {note: start_time}
    
    # Iterate over time in fixed steps.
    for t in range(0, final_time + step_size, step_size):
        # Process all events that occur at or before time t.
        while event_index < len(events) and events[event_index][0] <= t:
            event_time, msg = events[event_index]
            if msg.type == 'note_on':
                if msg.velocity > 0:
                    # Note on event.
                    active_notes[msg.note] = event_time
                else:
                    # A note_on with velocity 0 is equivalent to note_off.
                    active_notes.pop(msg.note, None)
            elif msg.type == 'note_off':
                active_notes.pop(msg.note, None)
            event_index += 1
        
        if active_notes:
            # If multiple notes are active, choose the highest note.
            current_token = max(active_notes.keys())
        else:
            # No note is active: mark as rest (or a special token, like 0 or None)
            current_token = None
        tokens.append(current_token)
    
    return tokens


def trim_and_convert_nones(tokens, subdivision=1):
    """
    Trim leading/trailing Nones in subdivision multiples, convert all Nones to -1.
    
    Example (subdivision=4):
    Input: [None, None, None, None, None, 60, None, 62, None, None, None]
    Output: [-1, 60, -1, 62, -1]  # Trimmed 4 leading/trailing Nones, kept 1
    """
    if not tokens:
        return []
    
    # Find first non-None index
    first = 0
    while first < len(tokens) and tokens[first] is None:
        first += 1
    
    # Find last non-None index
    last = len(tokens) - 1
    while last >= 0 and tokens[last] is None:
        last -= 1
    
    # Handle all-None case
    if first > last:
        return []
    
    # Calculate trimming boundaries
    leading_remove = (first // subdivision) * subdivision
    trailing_remove = ((len(tokens) - last - 1) // subdivision) * subdivision
    
    new_first = leading_remove
    new_last = len(tokens) - trailing_remove - 1
    
    # Apply trimming
    trimmed = tokens[new_first:new_last+1]
    
    # Convert ALL Nones to -1
    return [x if x is not None else -1 for x in trimmed]


def replace_neg1_with_none(lst):
    """Replace all occurrences of -1 with None in a list."""
    return [None if x == -1 else x for x in lst]