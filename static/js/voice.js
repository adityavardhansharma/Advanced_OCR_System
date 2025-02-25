// static/js/voice.js

// Elements for recording UI
const startButton = document.getElementById('startRecording');
const stopButton = document.getElementById('stopRecording');
const recordingIndicator = document.getElementById('recordingIndicator');
const statusMessage = document.getElementById('statusMessage');
const timerDisplay = document.getElementById('timer');
const processingIndicator = document.getElementById('processingIndicator');
const audioForm = document.getElementById('audioForm');

// MediaRecorder variables
let mediaRecorder;
let audioChunks = [];
let startTime;
let timerInterval;

// Check if recording is supported
if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
  // Setup is supported
  startButton.addEventListener('click', startRecording);
  stopButton.addEventListener('click', stopRecording);
} else {
  // Not supported
  statusMessage.textContent = "Recording not supported in this browser";
  startButton.disabled = true;
  document.querySelector('.voice-instructions').innerHTML =
    "<p class='error-message'>Your browser doesn't support audio recording. " +
    "Please try Chrome, Firefox, or Edge.</p>";
}

// Start recording function
async function startRecording() {
  try {
    // Request microphone access
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

    // Create media recorder with explicit audio type (if supported)
    const options = { mimeType: 'audio/webm' };
    try {
      mediaRecorder = new MediaRecorder(stream, options);
    } catch (e) {
      // Browser doesn't support specified format, use default
      console.log("WebM format not supported, using default format");
      mediaRecorder = new MediaRecorder(stream);
    }

    audioChunks = [];

    // Event for data available
    mediaRecorder.addEventListener('dataavailable', event => {
      audioChunks.push(event.data);
    });

    // Start recording
    mediaRecorder.start();

    // Update UI to show recording state
    recordingIndicator.classList.add('active');
    statusMessage.textContent = "Recording... Speak now";
    startButton.disabled = true;
    stopButton.disabled = false;

    // Start timer
    startTime = Date.now();
    updateTimer();
    timerInterval = setInterval(updateTimer, 1000);

  } catch (error) {
    console.error("Error starting recording:", error);
    statusMessage.textContent = "Error: " + (error.message || "Could not access microphone");
  }
}

// Stop recording function
function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    // Stop the media recorder
    mediaRecorder.stop();

    // Stop all tracks in the stream
    mediaRecorder.stream.getTracks().forEach(track => track.stop());

    // Stop the timer
    clearInterval(timerInterval);

    // Update UI
    recordingIndicator.classList.remove('active');
    statusMessage.textContent = "Processing your recording...";
    startButton.disabled = true;
    stopButton.disabled = true;
    processingIndicator.classList.remove('hidden');

    // When recording is actually complete and data is ready
    mediaRecorder.addEventListener('stop', () => {
      // Create audio blob with the correct MIME type
      const mimeType = mediaRecorder.mimeType || 'audio/webm';
      const audioBlob = new Blob(audioChunks, { type: mimeType });

      // Create audio element for playback verification (optional)
      const audioURL = URL.createObjectURL(audioBlob);
      const audio = document.createElement('audio');
      audio.style.display = 'none';
      audio.src = audioURL;
      document.body.appendChild(audio);

      // Submit the audio data with correct format
      submitAudioData(audioBlob, mimeType);
    });
  }
}

// Update the timer display
function updateTimer() {
  const elapsedTime = Date.now() - startTime;
  const seconds = Math.floor(elapsedTime / 1000) % 60;
  const minutes = Math.floor(elapsedTime / 60000);

  timerDisplay.textContent =
    `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
}

// Submit the audio data to the server
function submitAudioData(audioBlob, mimeType) {
  // Create form data with audio blob
  const formData = new FormData();

  // Use the correct extension based on MIME type
  let extension = 'webm';
  if (mimeType.includes('mp4') || mimeType.includes('mp4a')) {
    extension = 'mp4';
  } else if (mimeType.includes('ogg')) {
    extension = 'ogg';
  }

  formData.append('audio', audioBlob, `recording.${extension}`);
  formData.append('mime_type', mimeType); // Send MIME type to server

  // Send the data
  fetch('/process_voice', {
    method: 'POST',
    body: formData
  })
  .then(response => {
    if (!response.ok) {
      throw new Error('Server error: ' + response.status);
    }
    return response.text();
  })
  .then(html => {
    // Replace the current page with the result page
    document.open();
    document.write(html);
    document.close();
  })
  .catch(error => {
    console.error('Error:', error);
    statusMessage.textContent = 'Error processing recording. Please try again.';
    processingIndicator.classList.add('hidden');
    startButton.disabled = false;
  });
}
