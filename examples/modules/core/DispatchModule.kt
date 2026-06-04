package com.yuangungun.os.core.dispatch

import kotlinx.coroutines.*
import java.util.concurrent.ConcurrentHashMap

/**
 * Task dispatcher with priority queue.
 * Manages concurrent task execution with lifecycle awareness.
 */
class DispatchModule(
    private val maxConcurrent: Int = 4
) : CoroutineScope {
    private val job = SupervisorJob()
    private val scope = CoroutineScope(Dispatchers.Default + job)
    private val activeTasks = ConcurrentHashMap<String, Job>()
    private val taskQueue = PriorityQueue<Task>()

    suspend fun submit(
        taskId: String,
        priority: Int = 0,
        block: suspend () -> Unit
    ): Boolean {
        if (activeTasks.size >= maxConcurrent) {
            taskQueue.offer(Task(taskId, priority, block))
            return false
        }

        val job = scope.launch { block() }
        activeTasks[taskId] = job
        job.invokeOnCompletion {
            activeTasks.remove(taskId)
            dispatchNext()
        }
        return true
    }

    private fun dispatchNext() {
        scope.launch {
            taskQueue.poll()?.let { task ->
                val job = scope.launch { task.block() }
                activeTasks[task.id] = job
                job.invokeOnCompletion {
                    activeTasks.remove(task.id)
                    dispatchNext()
                }
            }
        }
    }

    fun cancel(taskId: String) {
        activeTasks[taskId]?.cancel()
        activeTasks.remove(taskId)
    }

    fun cancelAll() {
        scope.cancel()
    }

    fun getActiveCount(): Int = activeTasks.size
    fun getQueueSize(): Int = taskQueue.size

    private data class Task(
        val id: String,
        val priority: Int,
        val block: suspend () -> Unit
    ) : Comparable<Task> {
        override fun compareTo(other: Task): Int = other.priority.compareTo(priority)
    }
}
