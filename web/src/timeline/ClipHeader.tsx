import { lengthWords, placeWords } from './clipPanel'
import type { ClipPlace } from './clipPanel'

/*
 * The inspector's Clip tab opens with the selected clip: its name, its chapter and place in it,
 * and how long it is in the movie (`editor-selection`). Display only.
 */

export function ClipHeader({ place }: { place: ClipPlace }) {
  return (
    <header className="tl-clip-head">
      <h3 className="tl-clip-name">{place.name}</h3>
      <p className="tl-clip-where">{placeWords(place)}</p>
      <p className="tl-clip-length">{lengthWords(place)}</p>
    </header>
  )
}
