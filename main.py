import os
from src.midi_processing import generate_midi_from_tokens,\
    process_midi_file,\
    trim_and_convert_nones,\
    replace_neg1_with_none
from src.jazzgpt import JazzGpt


if __name__ == '__main__':
    folder_path = './data/jazzmidi/'  # Replace with the path to your folder
    # midi_files = [f for f in os.listdir(folder_path) if f.endswith('.mid')]
    midi_files = ['AutumnLeaves.mid']
    
    midi_data = {}
    sample_frequency_per_beat = 6

    for midi_file_name in midi_files:
        print(midi_file_name)
        file_path = os.path.join(folder_path, midi_file_name)
        try:
            midi_data[midi_file_name] = process_midi_file(file_path,
                                                          track_name='solo',
                                                          subdivision=sample_frequency_per_beat)
        except:
            print('Cannot extract the tracks from the MIDI file.')

    midi_example = midi_data.get('AutumnLeaves.mid')

    generate_midi_from_tokens(tokens=midi_example['notes'],
                              output_file_name='training.mid',
                              ticks_per_beat=midi_example['ticks_per_beat'],
                              subdivision=midi_example['sample_steps_per_beat'])

    jazz_gpt = JazzGpt(trim_and_convert_nones(midi_example['notes'],
                                              subdivision=midi_example['sample_steps_per_beat']))
    jazz_gpt.jazzgpt_training()
    generated_notes = jazz_gpt.generate_music_from_notes(initial_notes=[-1, -1, 57, 57, 62, 62],
                                                         next_n=2000)

    generate_midi_from_tokens(tokens=replace_neg1_with_none(generated_notes),
                              output_file_name='generation.mid',
                              ticks_per_beat=midi_example['ticks_per_beat'],
                              subdivision=midi_example['sample_steps_per_beat'])
