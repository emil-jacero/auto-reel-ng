import type { PreviewResult } from '../../api/titleCard.ts'
import type { PreviewAnswer } from './preview.ts'

/** The client's result as the preview controller reads it: a problem becomes its words. */
export function answerOf(result: PreviewResult): PreviewAnswer {
  switch (result.kind) {
    case 'image':
      return { kind: 'image', png: result.png }
    case 'refused':
      return { kind: 'refused', detail: result.problem.detail }
    case 'gone':
      return { kind: 'gone', detail: result.problem.detail }
    case 'bound':
      return { kind: 'bound', message: result.message }
    case 'failed':
      return { kind: 'failed', detail: result.problem.detail }
    case 'busy':
      return { kind: 'busy', retryAfter: result.retryAfter }
    case 'unreachable':
      return { kind: 'unreachable' }
    case 'unpublished':
      return { kind: 'unpublished', message: result.message }
  }
}
