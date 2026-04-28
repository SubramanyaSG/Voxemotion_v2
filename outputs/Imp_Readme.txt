while running the train.py you will get below error
Traceback (most recent call last):
  File "Your_path\Voxemotion_v2\train.py", line 174, in <module>
    main()
  File "Your_path\Voxemotion_v2\train.py", line 143, in main
    plot_mel_spectrograms(df)
  File "Your_path\Voxemotion_v2\train.py", line 47, in plot_mel_spectrograms
    audio, sr = load_audio(row['file'], target_sr=SAMPLE_RATE)
  File "Your_path\Voxemotion_v2\utils\audio.py", line 43, in load_audio
    data, sr = sf.read(path, dtype='float32', always_2d=False)
  File "Your_path\Voxemotion_v2\venv\lib\site-packages\soundfile.py", line 285, in read
    with SoundFile(file, 'r', samplerate, channels,
  File "Your_path\Voxemotion_v2\venv\lib\site-packages\soundfile.py", line 658, in __init__
    self._file = self._open(file, mode_int, closefd)
  File "Your_path\Voxemotion_v2\venv\lib\site-packages\soundfile.py", line 1216, in _open
    raise LibsndfileError(err, prefix="Error opening {0!r}: ".format(self.name))
soundfile.LibsndfileError: Error opening 'D:\\Downloads\\tts_emotion_project_v2\\Emotion Speech Dataset1
\\English\\0011\\Angry\\0011_000351.wav': System error. 

so to avoid the error just delete the dataset_metadata.csv before running the train.py