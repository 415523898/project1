<script setup lang="ts">
import { cancelDisclosure, enterDisclosure, leaveDisclosure } from '@/utils/disclosure-motion';
</script>

<template>
  <Transition
    :css="false"
    @enter="enterDisclosure"
    @leave="leaveDisclosure"
    @enter-cancelled="cancelDisclosure"
    @leave-cancelled="cancelDisclosure"
    ><slot
  /></Transition>
</template>
