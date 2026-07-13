/*
 * FreeRTOS V202212.00
 * Copyright (C) 2020 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of
 * this software and associated documentation files (the "Software"), to deal in
 * the Software without restriction, including without limitation the rights to
 * use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
 * the Software, and to permit persons to whom the Software is furnished to do so,
 * subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
 * FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
 * COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
 * IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 * CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 *
 * https://www.FreeRTOS.org
 * https://github.com/FreeRTOS
 *
 */

/******************************************************************************
 * This project provides two demo applications.  A simple blinky style project,
 * and a more comprehensive test and demo application.  The
 * mainCREATE_SIMPLE_BLINKY_DEMO_ONLY setting in main.c is used to select
 * between the two.  See the notes on using mainCREATE_SIMPLE_BLINKY_DEMO_ONLY
 * in main.c.  This file implements the simply blinky version.
 *
 * This file only contains the source code that is specific to the basic demo.
 * Generic functions, such FreeRTOS hook functions, are defined in main.c.
 ******************************************************************************
 *
 * main_blinky() creates one queue, one software timer, and two tasks.  It then
 * starts the scheduler.
 *
 * The Queue Send Task:
 * The queue send task is implemented by the prvQueueSendTask() function in
 * this file.  It uses vTaskDelayUntil() to create a periodic task that sends
 * the value 100 to the queue every 200 (simulated) milliseconds.
 *
 * The Queue Send Software Timer:
 * The timer is an auto-reload timer with a period of two (simulated) seconds.
 * Its callback function writes the value 200 to the queue.  The callback
 * function is implemented by prvQueueSendTimerCallback() within this file.
 *
 * The Queue Receive Task:
 * The queue receive task is implemented by the prvQueueReceiveTask() function
 * in this file.  prvQueueReceiveTask() waits for data to arrive on the queue.
 * When data is received, the task checks the value of the data, then outputs a
 * message to indicate if the data came from the queue send task or the queue
 * send software timer.
 */

/* Standard includes. */
#include <stdio.h>

/* Kernel includes. */
#include "FreeRTOS.h"
#include "task.h"
#include "timers.h"
#include "queue.h"
#include "semphr.h"

/* Priorities at which the tasks are created. */
#define mainQUEUE_RECEIVE_TASK_PRIORITY    ( tskIDLE_PRIORITY + 2 )
#define mainQUEUE_SEND_TASK_PRIORITY       ( tskIDLE_PRIORITY + 1 )

/* The rate at which data is sent to the queue.  The times are converted from
 * milliseconds to ticks using the pdMS_TO_TICKS() macro. */
#define mainTASK_SEND_FREQUENCY_MS         pdMS_TO_TICKS( 500UL )
#define mainTIMER_SEND_FREQUENCY_MS        pdMS_TO_TICKS( 3000UL )

/* The number of items the queue can hold at once. */
#define mainQUEUE_LENGTH                   ( 2 )

/* The values sent to the queue receive task from the queue send task and the
 * queue send software timer respectively. */
#define mainVALUE_SENT_FROM_TASK           ( 100UL )
#define mainVALUE_SENT_FROM_TIMER          ( 200UL )

/*-----------------------------------------------------------*/

/*
 * The tasks as described in the comments at the top of this file.
 */
static void prvQueueReceiveTask( void * pvParameters );
static void prvQueueSendTask( void * pvParameters );
static void vControlTask( void * pvParameters );
static void vSensorTask( void * pvParameters );
static void vMonitorTask( void * pvParameters );

/*
 * The callback function executed when the software timer expires.
 */
static void prvQueueSendTimerCallback( TimerHandle_t xTimerHandle );

/*-----------------------------------------------------------*/

/* The queue used by both tasks. */
static QueueHandle_t xQueue = NULL;

/* A software timer that is started from the tick hook. */
static TimerHandle_t xTimer = NULL;
typedef struct
{
    uint32_t sensorValue;
    uint32_t setpoint;
    int32_t controlOutput;
} ControlState_t;

static ControlState_t xControlState = { 0U, 50U, 0 };
static SemaphoreHandle_t xStateMutex = NULL;

/*-----------------------------------------------------------*/

/*** SEE THE COMMENTS AT THE TOP OF THIS FILE ***/
void main_blinky( void )
{
    xStateMutex = xSemaphoreCreateMutex();

    if( xStateMutex != NULL )
    {
        xTaskCreate( vControlTask,
                     "Ctrl",
                     configMINIMAL_STACK_SIZE,
                     NULL,
                     tskIDLE_PRIORITY + 4,
                     NULL );

        xTaskCreate( vSensorTask,
                     "Sensor",
                     configMINIMAL_STACK_SIZE,
                     NULL,
                     tskIDLE_PRIORITY + 3,
                     NULL );

        xTaskCreate( vMonitorTask,
                     "Monitor",
                     configMINIMAL_STACK_SIZE * 2,
                     NULL,
                     tskIDLE_PRIORITY + 1,
                     NULL );

        vTaskStartScheduler();
    }

    for( ; ; )
    {
    }
}
/*-----------------------------------------------------------*/

static void prvQueueSendTask( void * pvParameters )
{
    TickType_t xNextWakeTime;
    const TickType_t xBlockTime = mainTASK_SEND_FREQUENCY_MS;
    const uint32_t ulValueToSend = mainVALUE_SENT_FROM_TASK;

    /* Prevent the compiler warning about the unused parameter. */
    ( void ) pvParameters;

    /* Initialise xNextWakeTime - this only needs to be done once. */
    xNextWakeTime = xTaskGetTickCount();

    for( ; ; )
    {
        /* Place this task in the blocked state until it is time to run again.
         * The block time is specified in ticks, pdMS_TO_TICKS() was used to
         * convert a time specified in milliseconds into a time specified in ticks.
         * While in the Blocked state this task will not consume any CPU time. */      
        vTaskDelayUntil( &xNextWakeTime, xBlockTime );

        /* Send to the queue - causing the queue receive task to unblock and
         * write to the console.  0 is used as the block time so the send operation
         * will not block - it shouldn't need to block as the queue should always
         * have at least one space at this point in the code. */
        xQueueSend( xQueue, &ulValueToSend, 0U );
    }
}
/*-----------------------------------------------------------*/

static void prvQueueSendTimerCallback( TimerHandle_t xTimerHandle )
{
    const uint32_t ulValueToSend = mainVALUE_SENT_FROM_TIMER;

    /* This is the software timer callback function.  The software timer has a
     * period of two seconds and is reset each time a key is pressed.  This
     * callback function will execute if the timer expires, which will only happen
     * if a key is not pressed for two seconds. */

    /* Avoid compiler warnings resulting from the unused parameter. */
    ( void ) xTimerHandle;

    /* Send to the queue - causing the queue receive task to unblock and
     * write out a message.  This function is called from the timer/daemon task, so
     * must not block.  Hence the block time is set to 0. */
    xQueueSend( xQueue, &ulValueToSend, 0U );
}
/*-----------------------------------------------------------*/

static void prvQueueReceiveTask( void * pvParameters )
{
    uint32_t ulReceivedValue;

    /* Prevent the compiler warning about the unused parameter. */
    ( void ) pvParameters;

    /* TraceRecorder: Registering a channel name for the user events. */
    TraceStringHandle_t xUserEventLogChannel;
    xTraceStringRegister("Log", &xUserEventLogChannel);

    for( ; ; )
    {
        /* Wait until something arrives in the queue - this task will block
         * indefinitely provided INCLUDE_vTaskSuspend is set to 1 in
         * FreeRTOSConfig.h.  It will not use any CPU time while it is in the
         * Blocked state. */
        xQueueReceive( xQueue, &ulReceivedValue, portMAX_DELAY );

        /*  To get here something must have been received from the queue, but
         * is it an expected value? */
        if( ulReceivedValue == mainVALUE_SENT_FROM_TASK )
        {
            /* It is normally not good to call printf() from an embedded system,
             * although it is ok in this simulated case. */
            printf( "Message received from task\r\n" );

            /******************************************************************
             * TODO TraceRecorder (Tweak 5): Added User Events (xTracePrint).
             * Can be a better alternative to printf (faster and thread-safe).
             * xTracePrint is similar to puts(), i.e. strings only.
             * xTracePrintF is similar to printf (with integer arguments).
             * Examples:
             *  xTracePrint(channel, "Something happened!");
             *  xTracePrintF(channel, "Value 1: %d, Value 2: %d", val1, val2);
             * See trcPrint.h for details.
             *****************************************************************/
            xTracePrint(xUserEventLogChannel, "Message received from task");
        }
        else if( ulReceivedValue == mainVALUE_SENT_FROM_TIMER )
        {
            printf( "Message received from software timer\r\n" );

            xTracePrint(xUserEventLogChannel,
            		"Message received from software timer");
        }
        else
        {
            printf( "Unexpected message\r\n" );

            xTracePrint(xUserEventLogChannel, "Unexpected message");
        }
    }
}
/*-----------------------------------------------------------*/
static void vSensorTask( void * pvParameters )
{
    TickType_t xLastWakeTime = xTaskGetTickCount();
    uint32_t ulSensorValue = 0U;

    ( void ) pvParameters;

    for( ; ; )
    {
        ulSensorValue = ( ulSensorValue + 7U ) % 101U;

        if( xSemaphoreTake( xStateMutex, pdMS_TO_TICKS( 2U ) ) == pdTRUE )
        {
            xControlState.sensorValue = ulSensorValue;
            xSemaphoreGive( xStateMutex );
        }

        vTaskDelayUntil( &xLastWakeTime, pdMS_TO_TICKS( 10U ) );
    }
}
static void vControlTask( void * pvParameters )
{
    TickType_t xLastWakeTime = xTaskGetTickCount();

    ( void ) pvParameters;

    for( ; ; )
    {
        if( xSemaphoreTake( xStateMutex, pdMS_TO_TICKS( 1U ) ) == pdTRUE )
        {
            int32_t lError = ( int32_t ) xControlState.setpoint -
                             ( int32_t ) xControlState.sensorValue;

            xControlState.controlOutput = lError * 2;

            xSemaphoreGive( xStateMutex );
        }

        vTaskDelayUntil( &xLastWakeTime, pdMS_TO_TICKS( 1U ) );
    }
}
static void prvPrintUnsigned( uint32_t ulValue )
{
    char cBuffer[ 11 ];
    int i = 10;

    cBuffer[ i ] = '\0';

    do
    {
        cBuffer[ --i ] = ( char ) ( '0' + ( ulValue % 10U ) );
        ulValue /= 10U;
    } while( ulValue != 0U );

    printf( &cBuffer[ i ] );
}

static void prvPrintSigned( int32_t lValue )
{
    if( lValue < 0 )
    {
        printf( "-" );
        prvPrintUnsigned( ( uint32_t ) ( -lValue ) );
    }
    else
    {
        prvPrintUnsigned( ( uint32_t ) lValue );
    }
}
static void vMonitorTask( void * pvParameters )
{
    TickType_t xLastWakeTime = xTaskGetTickCount();
    uint32_t ulSensorValue;
    uint32_t ulSetpoint;
    int32_t lControlOutput;

    ( void ) pvParameters;

    for( ; ; )
    {
        if( xSemaphoreTake( xStateMutex, pdMS_TO_TICKS( 10U ) ) == pdTRUE )
        {
            ulSensorValue = xControlState.sensorValue;
            ulSetpoint = xControlState.setpoint;
            lControlOutput = xControlState.controlOutput;

            xSemaphoreGive( xStateMutex );

            printf( "sensor=" );
            prvPrintUnsigned( ulSensorValue );

            printf( " setpoint=" );
            prvPrintUnsigned( ulSetpoint );

            printf( " output=" );
            prvPrintSigned( lControlOutput );

            printf( "\r\n" );
        }

        vTaskDelayUntil( &xLastWakeTime, pdMS_TO_TICKS( 1000U ) );
    }
}