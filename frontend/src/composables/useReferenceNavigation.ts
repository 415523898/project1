import { readonly, ref } from 'vue'

const overviewRequest = ref(0)

export function useReferenceNavigation() {
  return {
    overviewRequest: readonly(overviewRequest),
    openOverview() {
      overviewRequest.value++
    },
  }
}
