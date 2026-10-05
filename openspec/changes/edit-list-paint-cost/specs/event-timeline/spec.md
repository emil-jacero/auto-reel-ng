## ADDED Requirements

### Requirement: Zooming, scrubbing and playing leave the Edit page around the Timeline alone

In Edit mode, zooming the Timeline (the Zoom slider, the zoom buttons and keys, Ctrl/Cmd+wheel), scrubbing the
playhead and playing SHALL NOT re-render any clip row of the page's clip list, nor any other part of the page outside the
Timeline, and SHALL NOT make the browser repaint the clip rows that are out of view.

A drag of the Zoom slider SHALL stay smooth on a large event: for an event of 400 clips in one chapter, in a
1280 × 900 window with the Timeline in view, a scripted drag of the slider from its left end to its right end and back
in 180 pointer moves SHALL take longer than 25 ms for at most 2 % of its frames, as the median of at least five runs in
Chrome 154 under a 4x CPU throttle and of at least three runs unthrottled in Firefox 155 or newer. Each figure SHALL be
recorded with the same page's idle figure (the same frame count with no drag) from the same session. The Timeline's
scrub (at least 30 distinct frames presented per second) and frame-step (90th percentile at most 60 ms) figures SHALL
still hold on the same event.

#### Scenario: A zoom renders no clip row
- **WHEN** the Timeline of an event of 400 clips is zoomed with the slider from Fit to 240 px per second, the playhead
  is scrubbed across 20 clips, and the Timeline plays for 5 s
- **THEN** a render count of the clip rows, taken in a measurement build, is the same before and after

#### Scenario: The slider drag on 400 clips is smooth in Chrome
- **WHEN** the scripted 180-move slider drag runs five times on the 400-clip event in Chrome 154 at a 4x CPU throttle
- **THEN** the median share of frames over 25 ms is at most 2 %, recorded with the idle page's share from the same
  session

#### Scenario: The slider drag on 400 clips is smooth in Firefox
- **WHEN** the same drag runs three times unthrottled in Firefox 155 or newer
- **THEN** the median share of frames over 25 ms is at most 2 %

#### Scenario: The scrub gates still hold
- **WHEN** the scrub and frame-step scripts run on the 400-clip event in Chrome 154 and in Firefox 155 or newer
- **THEN** the scrub presents a median of at least 30 distinct frames per second and the frame-step 90th percentile is
  at most 60 ms in each
