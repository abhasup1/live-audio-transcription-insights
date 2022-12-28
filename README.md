# Live Transcription With Python and FastAPI

To run this project locally install dependencies first

```
pip install -r requirements.txt
```

Make sure you're in the directory with the **main.py** file and run the project in the development server.

```
uvicorn main:app --reload
```

Pull up a browser and go to your localhost, http://127.0.0.1:8000/.

Allow access to your microphone and start speaking. A transcript of your audio will appear in the browser and also get pushed to mongo-db</br>
Schema of mongo-db document

```
{'_id': 'http://www.phoneix-hackathon-meet',
 'attendees': {'abhas': {'transcript': ['Hello.',
    'Are you able to hear me?',
    'Are you able to log this also?',
    'Yeah. I think we should be.',
    "Let's see if it",
    'gets registered somewhere.',
    "I'm taking pause.",
    "Let's it",
    'Hello. This is Ab testing voice recording.',
    'I spoke one sentence.',
    'Took a pause.',
    'Now spoke another one.']}}}
```

**Deploy**

The code is deployed via helm in kubernetes as a fast-api deployment. Use the code below to first build image and then deploy :-

```
1) docker build -t <imag_name> .

2) helm upgrade --install live-transcription <helm-chart-name> --version <helm-chart-version> -f values-dev.yaml

```



